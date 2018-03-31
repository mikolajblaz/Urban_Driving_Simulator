import numpy as np
from gym_urbandriving.utils.PID import PIDController
from gym_urbandriving.agents import PursuitAgent
from gym_urbandriving.planning import VelocityMPCPlanner,GeometricPlanner
from copy import deepcopy
import gym_urbandriving as uds

class VelocityActionAgent(PursuitAgent):
    """
    Hierarichal agent which implements the full plannning stack except the velocity component
    The planner first generates a nominal trajecotry, then at each timestep recives a target velocity
    to track with PID controller. 


    Attributes
    ----------
    agent_num : int
        Index of this agent in the world.
        Used to access its object in state.dynamic_objects

    """

    def __init__(self, agent_num=0):
        """
        Initializes the VelocityActionAgent Class

        Parameters
        ----------
        agent_num: int
            The number which specifies the agent in the dictionary state.dynamic_objects['controlled_cars']

        """

        self.agent_num = agent_num
        #Move to JSON 
        self.PID_acc = PIDController(1.0, 0, 0)
        self.PID_steer = PIDController(2.0, 0, 0)
        self.not_initiliazed = True
        

        
    def eval_policy(self, action,state):
        """
        Returns action based next state in trajectory. 

        Parameters
        ----------
        state : PositionState
            State of the world, unused
        action : float or None
            Target velocity for car to travel at 

        Returns
        -------
        tuple with floats (steering,acceleration)
        """

        if not (type(action) == float or action == None):
           raise Exception('Velocity Action is not of type float')

        if self.not_initiliazed:
            geoplanner = GeometricPlanner(deepcopy(state), inter_point_d=40.0, planning_time=0.1)

            geoplanner.plan_for_agents(state,type_of_agent='controlled_cars',agent_num=self.agent_num)
            self.not_initiliazed = False

        
        target_vel = action
        state.dynamic_objects['controlled_cars'][str(self.agent_num)].trajectory.set_vel(target_vel)

        return super(VelocityActionAgent, self).eval_policy(state,type_of_agent='controlled_cars')

