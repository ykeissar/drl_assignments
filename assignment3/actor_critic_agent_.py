import tensorflow.compat.v1 as tf
import collections
import numpy as np

tf.disable_v2_behavior()


class ActorCriticAgent:
    def __init__(self, env=None, discount_factor=0.999, learning_rate=0.0002, v_learning_rate=0.005, render=False,
                 state_size=4, max_episodes=5000, max_steps=501):
        self.discount_factor = discount_factor
        self.learning_rate = learning_rate
        self.v_learning_rate = v_learning_rate
        self.render = render

        self.env = env
        self.state_size = env.observation_space.n if hasattr(env.observation_space, 'n') else env.observation_space.shape[0]
        self.action_size = env.action_space.n if hasattr(env.action_space, 'n') else env.action_space.shape[0]

        self.max_episodes = max_episodes
        self.max_steps = max_steps

        self.padded_state_size = 6
        self.padded_action_size = 20

        tf.reset_default_graph()
        self.policy = PolicyNetwork(self.padded_state_size, self.padded_action_size, self.learning_rate)
        self.value = ValueNetwork(self.padded_state_size, self.v_learning_rate)

        self.curr_env_name = ''

    def train(self):
        # Start training the agent with REINFORCE algorithm
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            solved = False
            Transition = collections.namedtuple("Transition", ["state", "action", "reward", "next_state", "done"])
            episode_rewards = np.zeros(self.max_episodes)
            average_rewards = 0.0
            v_loss = []
            p_loss = []
            for episode in range(self.max_episodes):
                state = self.env.reset()
                state = state.reshape([1, self.state_size])

                I = 1
                for step in range(self.max_steps):
                    actions_distribution = self.policy.predict(state, sess)
                    action = self.get_action(actions_distribution)
                    next_state, reward, done, _ = self.take_step(action)
                    next_state = next_state.reshape([1, self.state_size])
                    episode_rewards[episode] += reward
                    if self.render:
                        self.env.render()

                    if done:
                        v_s_tag = 0
                    else:
                        v_s_tag = self.value.predict(next_state, sess)

                    v_s = self.value.predict(state, sess)
                    delta = reward + self.discount_factor * v_s_tag - v_s

                    if self.env.action_space.shape[0] == 1 and False:
                        act = actions_distribution
                    else:
                        act = np.zeros(self.action_size)
                        act[action] = 1

                    _, loss = self.value.update(state, reward + self.discount_factor*v_s_tag, sess)
                    v_loss.append(loss)
                    _, loss = self.policy.update(state, I * delta, act, sess)
                    p_loss.append(loss)
                    if done:
                        break

                    I *= self.discount_factor
                    state = next_state

                if episode > 98:
                    # Check if solved
                    average_rewards = np.mean(episode_rewards[(episode - 99):episode + 1])
                print(f"Episode {episode} Reward: {episode_rewards[episode]} Average over 100 episodes: {round(average_rewards, 2)}")
                if self.goal_reached(average_rewards):
                    print(' Solved at episode: ' + str(episode))
                    solved = True

                if solved:
                    return solved, episode, average_rewards, v_loss, p_loss

        return False, -1, average_rewards, [], []

    def get_action(self, actions_distribution):
        actions_distribution[self.action_size:] = 0
        if self.curr_env_name == 'MountainCarContinuous-v0' and False:
            return actions_distribution
        sum_p = sum(actions_distribution)
        actions_distribution = [i / sum_p for i in actions_distribution]

        return np.random.choice(np.arange(len(actions_distribution)), p=actions_distribution)

    def goal_reached(self, average_rewards):
        if self.curr_env_name == 'CartPole-v1':
            return average_rewards > 475
        if self.curr_env_name == 'Acrobot-v1':
            return average_rewards > -81
        if self.curr_env_name == 'MountainCarContinuous-v0':
            return average_rewards > 0

    def set_env(self, env_name):
        self.curr_env_name = env_name
        self.policy.set_env(env_name)

        if env_name == 'MountainCarContinuous-v0':
            self.action_size = self.padded_action_size

    def take_step(self, action):
        act = action
        if self.curr_env_name == 'MountainCarContinuous-v0':
            # discretesizing action, from [0:self.action_size] number to corelating [-1:1] value
            act = [round(action / ((self.action_size - 1) / 2) - 1, 2)]
        return self.env.step(act)


class PolicyNetwork:
    def __init__(self, state_size, action_size, learning_rate, name='policy_network'):
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.curr_env_name = ''

        with tf.variable_scope(name):
            self.state = tf.placeholder(tf.float32, [None, self.state_size], name="state")
            self.action = tf.placeholder(tf.int32, [self.action_size], name="action")
            self.delta = tf.placeholder(tf.float32, name="delta")

            self.W1 = tf.get_variable("W1", [self.state_size, 12], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b1 = tf.get_variable("b1", [12], initializer=tf.zeros_initializer())
            self.W2 = tf.get_variable("W2", [12, self.action_size], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b2 = tf.get_variable("b2", [self.action_size], initializer=tf.zeros_initializer())
            # self.W3 = tf.get_variable("W3", [12, self.action_size], initializer=tf.keras.initializers.glorot_normal(seed=0))
            # self.b3 = tf.get_variable("b3", [self.action_size], initializer=tf.zeros_initializer())

            self.Z1 = tf.add(tf.matmul(self.state, self.W1), self.b1)
            self.A1 = tf.nn.relu(self.Z1)
            # self.Z2 = tf.add(tf.matmul(self.A1, self.W2), self.b2)
            # self.A2 = tf.nn.relu(self.Z2)
            self.output = tf.add(tf.matmul(self.A1, self.W2), self.b2)

            # Softmax probability distribution over actions
            if self.curr_env_name == 'MountainCarContinuous-v0' and False:
                # self.actions_distribution = []
                self.actions_distribution = self.output
                self.diff = tf.nn.l2_loss(self.action[0] - self.output[0])
                self.loss = tf.reduce_mean(self.diff * self.delta)
                # need to add comparison to actual action!
            else:
                self.actions_distribution = tf.squeeze(tf.nn.softmax(self.output))
                # Loss with negative log probability
                self.neg_log_prob = tf.nn.softmax_cross_entropy_with_logits_v2(logits=self.output, labels=self.action)
                self.loss = tf.reduce_mean(self.neg_log_prob * self.delta)

            self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)

    def predict(self, state, sess):
        return sess.run(self.actions_distribution, {self.state: pad(state, self.state_size)})

    def update(self, state, delta, action, sess):
        feed_dict = {self.state: pad(state, self.state_size), self.delta: delta, self.action: pad(action, self.action_size)}

        return sess.run([self.optimizer, self.loss], feed_dict)

    def set_env(self, env_name):
        self.curr_env_name = env_name


class ValueNetwork:
    def __init__(self, state_size, learning_rate, name='value_network'):
        self.state_size = state_size
        self.learning_rate = learning_rate

        with tf.variable_scope(name):
            self.state = tf.placeholder(tf.float32, [None, self.state_size], name="v_state")
            self.delta = tf.placeholder(tf.float32, name="delta")
            self.target = tf.placeholder(tf.float32, name="target")
            # self.error = tf.placeholder(tf.float32, name="error")
            # self.z = tf.constant(0, dtype=tf.float32)

            self.W1 = tf.get_variable("v_W1", [self.state_size, 12], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b1 = tf.get_variable("v_b1", [12], initializer=tf.zeros_initializer())
            self.W2 = tf.get_variable("v_W2", [12, 1], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b2 = tf.get_variable("v_b2", [1], initializer=tf.zeros_initializer())
            # self.W3 = tf.get_variable("v_W3", [12, 12], initializer=tf.keras.initializers.glorot_normal(seed=0))
            # self.b3 = tf.get_variable("v_b3", [12], initializer=tf.zeros_initializer())
            # self.W4 = tf.get_variable("v_W4", [12, 12], initializer=tf.keras.initializers.glorot_normal(seed=0))
            # self.b4 = tf.get_variable("v_b4", [1], initializer=tf.zeros_initializer())

            self.Z1 = tf.add(tf.matmul(self.state, self.W1), self.b1)
            self.A1 = tf.nn.relu(self.Z1)
            # self.Z2 = tf.add(tf.matmul(self.A1, self.W2), self.b2)
            # self.A2 = tf.nn.relu(self.Z2)
            # self.Z3 = tf.add(tf.matmul(self.A1, self.W3), self.b3)
            # self.A3 = tf.nn.relu(self.Z3)
            self.output = tf.add(tf.matmul(self.A1, self.W2), self.b2)

            # Softmax probability distribution over actions
            self.v_s = tf.squeeze(self.output)
            # Loss with negative log probability
            self.loss = tf.losses.mean_squared_error(self.v_s, self.target)
            self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)

    def predict(self, state, sess):
        return sess.run(self.v_s, {self.state: pad(state, self.state_size)})

    def update(self, state, target, sess):
        feed_dict = {self.state: pad(state, self.state_size), self.target: target}
        return sess.run([self.optimizer, self.loss], feed_dict)


def pad(a, l):
    if len(a.shape) == 1:
        new = np.zeros((l,))
        new[:a.shape[0]] = a
    else:
        new = np.zeros((1, l))
        new[:, :a.shape[1]] = a
    return new