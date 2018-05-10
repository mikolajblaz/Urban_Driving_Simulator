import gym
from copy import deepcopy
from gym_urbandriving.agents import *
import gym_urbandriving as uds
import IPython
import numpy as np

from gym_urbandriving.assets import Car, TrafficLight, CrosswalkLight
from gym_urbandriving.utils.featurizer import Featurizer
from gym_urbandriving.planning.reward_fn import default_reward_function
class UrbanDrivingEnv(gym.Env):
    """
    This class controls the evolution of a world state.
    While the :class:`PositionState` represents the layout of objects in the scene,
    the :class:`UrbanDrivingEnv` controls the evolution of the scene, and manages background
    actors.

    Note
    -----
        This class is used both to represent the true, global state of the world, and
        as a search agent's internal view of the world.

    Parameters
    ----------
    config_data: Dict
        JSON config file is loaded into a dictonary specifing prameters 
    init_state : PositionState
        The starting state for this environment (Only needed if now JSON config file is used)
    reward_fn :
        A function which takes in one parameter, the :class:`PositionState`,
    randomize : bool
        Sets whether :func:`env._reset()` returns the environment to the initial state,
        or if it returns it to a random state generated by the state's :func:`randomize()`
        function
    """
    metadata = {'render.modes': ['human']}

    def __init__(self,
                 config_data={},
                 init_state= None,
                 reward_fn=default_reward_function,
                 randomize=False):
        
        self.reward_fn = reward_fn
        self.max_time = 500
        self.observation_type = 'raw'
        self.featurizer = Featurizer(config_data)
        if config_data:
            self.init_state = uds.state.PositionState(config_data)
            if config_data['environment']['visualize']:
                self.visualizer = uds.PyGameVisualizer(config_data, (800, 800))
            else:
                self.visualizer = None
            self.max_time = config_data['environment']['max_time']
            self.observation_type = config_data['recorded_data']['state_space']
            self.visualize_lidar = config_data['environment']['visualize_lidar']
            assert(self.observation_type in {'Q-LIDAR', 'raw', 'bmp'})
        else:
            self.init_state = init_state
            self.visualizer = None

        self.lidar_points = {}


        self.randomize = randomize
        self.statics_rendered = False
        self.dynamic_collisions, self.static_collisions, self.last_col = [], [], -1
        if (self.init_state):
            self._reset()


    def _step(self, action, background_simplified=False,supervisor=False):
        """
        The step function accepts a control for the 0th agent in the scene. Then, it queries
        all the background agents to determine their actions. Then, it updates the scene
        and returns.
        
        Parameters
        ----------
        action :
            An action for the agentnum object in the scene.
        agentnum : int
            The index for the object which the action is applied for.

        Returns
        -------
        PositionState
            State of the world after this step;
        float
            Reward calculated by :func:`self.reward_fn`,
        bool
            Whether we have timed out, or there is a collision)
        dict

        """
        assert(self.current_state is not None)
        # Get actions for all objects
        background_car_actions = []
        controlled_car_actions = []
        background_traffic_actions = []
        pedestrian_actions = []
        crosswalk_light_actions = []
        self.lidar_points = {}
        ### GET ALL ACTIONS ####
    
        for agent in self.current_state.bg_agents['background_cars']:
            background_car_actions.append(agent.eval_policy(self.current_state,simplified=background_simplified))

        for agent in self.current_state.bg_agents['traffic_lights']:
            background_traffic_actions.append(agent.eval_policy(self.current_state))

        for i,agent in enumerate(self.current_state.bg_agents['controlled_cars']):
            controlled_car_actions.append(agent.eval_policy(action[i],self.current_state,simplified=background_simplified))
        for i,agent in enumerate(self.current_state.bg_agents['pedestrians']):
            pedestrian_actions.append(agent.eval_policy(self.current_state))
        for i,agent in enumerate(self.current_state.bg_agents['crosswalk_lights']):
            crosswalk_light_actions.append(agent.eval_policy(self.current_state))



        ####UPDATE ALL POLICIES#########
        for index, dobj in self.current_state.dynamic_objects['background_cars'].items():
            dobj.step(background_car_actions[int(index)].get_value())

        for index, dobj in self.current_state.dynamic_objects['traffic_lights'].items():
            dobj.step(background_traffic_actions[int(index)])

        for i, dobj in self.current_state.dynamic_objects['controlled_cars'].items():
            if controlled_car_actions[int(i)] == None:
                IPython.embed()
            dobj.step(controlled_car_actions[int(i)].get_value())

        for i, dobj in self.current_state.dynamic_objects['pedestrians'].items():
            dobj.step(pedestrian_actions[int(i)])
        for i, dobj in self.current_state.dynamic_objects['crosswalk_lights'].items():
            dobj.step(crosswalk_light_actions[int(i)])

        self.current_state.time += 1
        dynamic_coll, static_coll, controlled_car_collisions = self.current_state.get_collisions()
        state = self.current_state
        reward = self.reward_fn(self.current_state)

        done = (self.current_state.time == self.max_time) or len(dynamic_coll) or len(static_coll)

        info_dict = {"saved_actions": action}

        if self.observation_type == 'raw':
            observations = [deepcopy(state) for i in state.dynamic_objects['controlled_cars']]
        elif self.observation_type == 'Q-LIDAR':
            observations = []
            for key in self.current_state.dynamic_objects['controlled_cars'].keys():
                obs = self.featurizer.featurize(self.current_state, key)
                observations.append(obs)
                self.lidar_points[key] = obs
        elif self.observation_type == 'bmp':
            assert(self.visualizer)
            self._render()
            observations = [self.visualizer.get_bitmap()] * len(state.dynamic_objects['controlled_cars'])
        if self.visualizer:
            self._render()

        return observations, reward, done, info_dict

    def get_initial_observations(self):
        if self.observation_type == 'raw':
            observations = [state] * len(state.dynamic_objects['controlled_cars'])
        elif self.observation_type == 'Q-LIDAR':
            observations = []
            for key in self.current_state.dynamic_objects['controlled_cars'].keys():
                obs = self.featurizer.featurize(self.current_state, key)
                observations.append(obs)
        elif self.observation_type == 'bmp':
            assert(self.visualizer)
            self._render()
            observations = [self.visualizer.get_bitmap()] * len(state.dynamic_objects['controlled_cars'])

        return observations

    def _reset(self, new_state=None):
        """
        Resets the environment to its initial state, or a new state
        
        Parameters
        ----------
        new_state : PositionState
            If specified, the environment will reset to this state
        """
        self.last_col = -1
        if new_state:
            self.init_state = new_state
            self.statics_rendered = False
        if self.randomize:
            self.init_state.randomize()

        self.current_state = deepcopy(self.init_state)

        return

    def _render(self, mode='human', close=False, waypoints=[],
                traffic_trajectories=[], transparent_surface=None):
        """
        If the renderer was specifed at construction, renders the current state of the world
        
        Parameters
        ----------
        mode : str
            For OpenAI Gym compatibility
        waypoints :
            Extra points you would like to render over top of the the scene, for debugging
        """

        if close:
            return
        if self.visualizer:
            
            window = [0, self.current_state.dimensions[0],
                      0, self.current_state.dimensions[1]]
            self.visualizer.render(self.current_state, window,
                                   rerender_statics= not self.statics_rendered,
                                   waypoints=waypoints,
                                   traffic_trajectories=traffic_trajectories,
                                   transparent_surface=transparent_surface,
                                   lidar_points=self.lidar_points if self.visualize_lidar else [])
            self.statics_rendered = True

    def get_current_state(self):
        return self.current_state

    def get_state_copy(self):
        return deepcopy(self.current_state)
