#!/usr/bin/env python


import rospy
import numpy as np
from std_msgs.msg import UInt8, Float64
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from enum import Enum
import math
import tf

def callback(x):    
    pass

class ControlParking():
    def __init__(self):
        self.showing_images = "off" # you can choose showing images or not by "on", "off"
        self.selecting_sub_image = "compressed" # you can choose image type "compressed", "raw"
        self.selecting_pub_image = "compressed" # you can choose image type "compressed", "raw"

        self.sub_lane = rospy.Subscriber('/control/lane', Float64, self.callback, queue_size = 1)

        self.sub_parking_start = rospy.Subscriber('/control/parking_start', UInt8, self.cbParkingStart, queue_size = 1)

        self.sub_odom = rospy.Subscriber('/odom', Odometry, self.cbOdom, queue_size=1)

        self.pub_cmd_vel = rospy.Publisher('/control/cmd_vel', Twist, queue_size = 1)

        self.pub_parking_finished = rospy.Publisher('/control/parking_finished', UInt8, queue_size = 1)

        self.lastError = 0

        self.StepOfParking = Enum('StepOfParking', 'idle outer_turn_first parking_lot_entry parking_lot_turn_first parking_lot_stop parking_lot_turn_second parking_lot_exit outer_turn_second')
        self.current_step_of_parking = self.StepOfParking.outer_turn_first.value

        self.is_step_parking = False

        self.theta = 0.0
        self.last_current_theta = 0.0
        
        self.is_step_start = False
        
        self.lastError = 0.0


        loop_rate = rospy.Rate(10) # 10hz
        while not rospy.is_shutdown():
            if self.is_step_parking == True:
                self.fnParking()
            
            loop_rate.sleep()

        rospy.on_shutdown(self.fnShutDown)

    def callback(self, desired_center):
        if self.is_step_parking == False:
            self.fnLaneFollow(desired_center)

    def cbParkingStart(self, parking_start_msg):
        self.is_step_parking = True
        self.lastError = 0.0

    def fnParking(self):
        if self.current_step_of_parking == self.StepOfParking.outer_turn_first.value:
            rospy.loginfo("outer_turn_first")
            if self.is_step_start == False:
                self.lastError = 0.0
                self.desired_theta = self.current_theta - 1.57
                self.is_step_start = True

            error = self.fnTurn()

            # rospy.loginfo("fnTurn error : %f ", error)
            if math.fabs(error) < 0.05:
                rospy.loginfo("outer_turn_first finished")
                self.current_step_of_parking = self.StepOfParking.parking_lot_entry.value
                self.is_step_start = False

        elif self.current_step_of_parking == self.StepOfParking.parking_lot_entry.value:
            rospy.loginfo("parking_lot_entry")
            if self.is_step_start == False:
                self.lastError = 0.0
                self.start_pos_x = self.current_pos_x
                self.start_pos_y = self.current_pos_y
                self.is_step_start = True

            error = self.fnStraight(0.25)

            if math.fabs(error) < 0.005:
                rospy.loginfo("parking_lot_entry finished")
                self.current_step_of_parking = self.StepOfParking.parking_lot_turn_first.value
                self.is_step_start = False            

        elif self.current_step_of_parking == self.StepOfParking.parking_lot_turn_first.value:
            rospy.loginfo("parking_lot_turn_first")
            if self.is_step_start == False:
                self.lastError = 0.0
                self.desired_theta = self.current_theta + 1.57
                self.is_step_start = True

            error = self.fnTurn()

            # rospy.loginfo("fnTurn error : %f ", error)
            if math.fabs(error) < 0.05:
                rospy.loginfo("parking_lot_turn_first finished")
                self.current_step_of_parking = self.StepOfParking.parking_lot_stop.value
                self.is_step_start = False

        elif self.current_step_of_parking == self.StepOfParking.parking_lot_stop.value:
            rospy.loginfo("parking_lot_stop")
            self.fnStop()

            rospy.sleep(2)

            rospy.loginfo("parking_lot_stop finished")
            self.current_step_of_parking = self.StepOfParking.parking_lot_turn_second.value

        elif self.current_step_of_parking == self.StepOfParking.parking_lot_turn_second.value:
            if self.is_step_start == False:
                rospy.loginfo("parking_lot_turn_second")
                self.lastError = 0.0
                self.desired_theta = self.current_theta + 1.57
                self.is_step_start = True

            error = self.fnTurn()

            # rospy.loginfo("fnTurn error : %f ", error)
            if math.fabs(error) < 0.05:
                rospy.loginfo("parking_lot_turn_second finished")
                self.current_step_of_parking = self.StepOfParking.parking_lot_exit.value
                self.is_step_start = False

        elif self.current_step_of_parking == self.StepOfParking.parking_lot_exit.value:
            rospy.loginfo("parking_lot_exit")
            if self.is_step_start == False:
                self.lastError = 0.0
                self.start_pos_x = self.current_pos_x
                self.start_pos_y = self.current_pos_y
                self.is_step_start = True

            error = self.fnStraight(0.25)

            if math.fabs(error) < 0.005:
                rospy.loginfo("parking_lot_exit finished")
                self.current_step_of_parking = self.StepOfParking.outer_turn_second.value
                self.is_step_start = False   

        elif self.current_step_of_parking == self.StepOfParking.outer_turn_second.value:
            rospy.loginfo("outer_turn_second")
            if self.is_step_start == False:
                self.lastError = 0.0
                self.desired_theta = self.current_theta - 1.57
                self.is_step_start = True

            error = self.fnTurn()

            # rospy.loginfo("fnTurn error : %f ", error)
            if math.fabs(error) < 0.05:
                rospy.loginfo("outer_turn_second finished")
                self.current_step_of_parking = self.StepOfParking.idle.value
                self.is_step_start = False

        else:
            rospy.loginfo("idle (if finished to go out from parking lot)")

            # self.current_step_of_parking = self.StepOfParking.outer_turn_first.value

            self.fnStop()

            msg_parking_finished = UInt8()
            msg_parking_finished.data = 1
            self.pub_parking_finished.publish(msg_parking_finished)

    def cbOdom(self, odom_msg):
		#  (self.now_roll, self.now_pitch, self.now_yaw) = tf.transformations.euler_from_quaternion([odom_msg.pose.pose.orientation.x, odom_msg.pose.pose.orientation.y, odom_msg.pose.pose.orientation.z, odom_msg.pose.pose.orientation.w])
        quaternion = (odom_msg.pose.pose.orientation.x, odom_msg.pose.pose.orientation.y, odom_msg.pose.pose.orientation.z, odom_msg.pose.pose.orientation.w)
        self.current_theta = self.euler_from_quaternion(quaternion)

        # rospy.loginfo("Got current theta : %f", self.current_theta)

        if (self.current_theta - self.last_current_theta) < -math.pi:
            # rospy.loginfo("subtract current theta : %f", self.current_theta - self.last_current_theta)
            # rospy.loginfo("it is gone to minus")
            self.current_theta = 2. * math.pi + self.current_theta
            self.last_current_theta = math.pi
        elif (self.current_theta - self.last_current_theta) > math.pi:
            # rospy.loginfo("subtract current theta : %f", self.current_theta - self.last_current_theta)
            # rospy.loginfo("it is gone to plus")
            self.current_theta = -2. * math.pi + self.current_theta
            self.last_current_theta = -math.pi
        else:
            self.last_current_theta = self.current_theta

        # rospy.loginfo("mod current theta : %f", self.current_theta)
        # rospy.loginfo("last current theta : %f", self.last_current_theta)

        self.current_pos_x = odom_msg.pose.pose.position.x
        self.current_pos_y = odom_msg.pose.pose.position.y
        # rospy.loginfo(self.)

    def euler_from_quaternion(self, quaternion):
        theta = tf.transformations.euler_from_quaternion(quaternion)[2]
        # if theta < 0:
        #     theta = theta + np.pi * 2
        # if theta > np.pi * 2:
        #     theta = theta - np.pi * 2
        return theta


    def fnLaneFollow(self, desired_center):

        rospy.loginfo("Parking_Lane_following")
        center = desired_center.data

        error = center - 500

        MAX_VEL = 0.10

        Kp = 0.0035#0.0035
        Kd = 0.007#0.007

        angular_z = Kp * error + Kd * (error - self.lastError)
        self.lastError = error

        # print(center)

        # print(error)
        # print(self.lastError)
        # print(angular_z)
        # print((1 - error / 500))       

        twist = Twist()
        twist.linear.x = MAX_VEL * ((1 - abs(error) / 500) ** 2) 
        twist.linear.y = 0
        twist.linear.z = 0
        twist.angular.x = 0
        twist.angular.y = 0
        twist.angular.z = -angular_z
        self.pub_cmd_vel.publish(twist)

    def fnTurn(self):
        err_theta = self.current_theta - self.desired_theta
        
        rospy.loginfo("Parking_Turn")
        rospy.loginfo("err_theta  desired_theta  current_theta : %f  %f  %f", err_theta, self.desired_theta, self.current_theta)
        Kp = 0.8#0.15

        Kd = 0.03#0.07

        angular_z = Kp * err_theta + Kd * (err_theta - self.lastError)
        self.lastError = err_theta

        twist = Twist()
        twist.linear.x = 0
        twist.linear.y = 0
        twist.linear.z = 0
        twist.angular.x = 0
        twist.angular.y = 0
        twist.angular.z = -angular_z
        self.pub_cmd_vel.publish(twist)

        rospy.loginfo("angular_z : %f", angular_z)

        return err_theta

    def fnStraight(self, desired_dist):
        err_pos = math.sqrt((self.current_pos_x - self.start_pos_x) ** 2 + (self.current_pos_y - self.start_pos_y) ** 2) - desired_dist
        
        rospy.loginfo("Parking_Straight")
        # rospy.loginfo("err_pos  desired_pos  current_pos : %f  %f  %f", err_pos, self.desired_pos, self.current_pos)

        Kp = 0.4#0.15
        Kd = 0.05#0.07

        angular_z = Kp * err_pos + Kd * (err_pos - self.lastError)
        self.lastError = err_pos

        twist = Twist()
        twist.linear.x = 0.07
        twist.linear.y = 0
        twist.linear.z = 0
        twist.angular.x = 0
        twist.angular.y = 0
        twist.angular.z = 0
        self.pub_cmd_vel.publish(twist)

        # rospy.loginfo("angular_z : %f", angular_z)

        return err_pos

    def fnStop(self):
        twist = Twist()
        twist.linear.x = 0
        twist.linear.y = 0
        twist.linear.z = 0
        twist.angular.x = 0
        twist.angular.y = 0
        twist.angular.z = 0
        self.pub_cmd_vel.publish(twist)


    def fnShutDown(self):
        rospy.loginfo("Shutting down. cmd_vel will be 0")

        twist = Twist()
        twist.linear.x = 0
        twist.linear.y = 0
        twist.linear.z = 0
        twist.angular.x = 0
        twist.angular.y = 0
        twist.angular.z = 0
        self.pub_cmd_vel.publish(twist) 

    def main(self):
        rospy.spin()



if __name__ == '__main__':
    rospy.init_node('control_parking')
    node = ControlParking()
    node.main()
