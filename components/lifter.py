import ctre
import magicbot
import wpilib


class Lifter:
    compressor: wpilib.Compressor
    motor: ctre.WPI_TalonSRX
    centre_switch: wpilib.DigitalInput
    top_switch: wpilib.DigitalInput

    #  TODO find encoder values, tune height values to include robot height and cube
    COUNTS_PER_REV = 4096
    NUM_TEETH = 42
    TEETH_DISTANCE = 0.005
    COUNTS_PER_METRE = COUNTS_PER_REV / (NUM_TEETH * TEETH_DISTANCE) / 2  # for height of dolly

    MOTOR_FREE_SPEED = 5840 / 600  # RPM to rotations/100ms
    GEAR_RATIO = 1 / 14
    FREE_SPEED = int(MOTOR_FREE_SPEED * GEAR_RATIO * COUNTS_PER_REV)  # counts/100ms

    TOP_HEIGHT = 2  # in m
    BOTTOM_HEIGHT = 0
    THRESHOLD = 0.005

    HEIGHT_FROM_FLOOR = 0.17  # height from floor to initial lift pos when reset in m
    CONTAINMENT_SIZE = 0  # height needed for the mechanism to work properly in m

    CUBE_HEIGHT = 0.5

    UPPER_SCALE = 1.8288 - HEIGHT_FROM_FLOOR + CONTAINMENT_SIZE + CUBE_HEIGHT  # in m
    BALANCED_SCALE = 1.524 - HEIGHT_FROM_FLOOR + CONTAINMENT_SIZE + CUBE_HEIGHT
    LOWER_SCALE = 1.2192 - HEIGHT_FROM_FLOOR + CONTAINMENT_SIZE + CUBE_HEIGHT
    SWITCH = 0.47625 - HEIGHT_FROM_FLOOR + CONTAINMENT_SIZE

    UPWARD_ACCELERATION = FREE_SPEED // 2
    DOWNWARD_ACCELERATION = FREE_SPEED // 2

    def setup(self):
        """This is called after variables are injected by magicbot."""
        self.set_pos = None

        self.motor.setQuadraturePosition(0, timeoutMs=10)
        self.motor.setInverted(True)
        self.motor.setNeutralMode(ctre.WPI_TalonSRX.NeutralMode.Brake)

        self.motor.overrideLimitSwitchesEnable(False)
        self.motor.configReverseLimitSwitchSource(ctre.WPI_TalonSRX.LimitSwitchSource.FeedbackConnector, ctre.WPI_TalonSRX.LimitSwitchNormal.NormallyOpen, deviceID=0, timeoutMs=10)
        self.motor.configForwardLimitSwitchSource(ctre.WPI_TalonSRX.LimitSwitchSource.Deactivated, ctre.WPI_TalonSRX.LimitSwitchNormal.Disabled, deviceID=0, timeoutMs=10)

        self.motor.overrideSoftLimitsEnable(True)
        self.motor.configForwardSoftLimitEnable(True, timeoutMs=10)
        self.motor.configForwardSoftLimitThreshold(self.metres_to_counts(self.TOP_HEIGHT), timeoutMs=10)
        self.motor.configReverseSoftLimitEnable(True, timeoutMs=10)
        self.motor.configReverseSoftLimitThreshold(self.metres_to_counts(self.BOTTOM_HEIGHT), timeoutMs=10)

        self.motor.configSelectedFeedbackSensor(ctre.WPI_TalonSRX.FeedbackDevice.QuadEncoder, 0, timeoutMs=10)

        # TODO tune motion profiling
        self.motor.selectProfileSlot(0, 0)
        self.motor.config_kF(0, 1023/self.FREE_SPEED, timeoutMs=10)
        self.motor.config_kP(0, 0.7, timeoutMs=10)
        self.motor.config_kI(0, 0, timeoutMs=10)
        self.motor.config_kD(0, 1, timeoutMs=10)

        self.motor.configMotionAcceleration(self.UPWARD_ACCELERATION, timeoutMs=10)
        self.motor.configMotionCruiseVelocity(int(self.FREE_SPEED*0.5), timeoutMs=10)

    def on_enable(self):
        """This is called whenever the robot transitions to being enabled."""

    def on_disable(self):
        """This is called whenever the robot transitions to disabled mode."""
        self.stop()

    def execute(self):
        """Run at the end of every control loop iteration."""

        if not self.centre_switch.get():
            self.motor.setSelectedSensorPosition(self.metres_to_counts(self.SWITCH), 0, timeoutMs=10)
        if not self.top_switch.get():
            self.motor.setSelectedSensorPosition(self.metres_to_counts(self.BALANCED_SCALE), 0, timeoutMs=10)
        if self.motor.isRevLimitSwitchClosed():
            self.motor.setSelectedSensorPosition(self.metres_to_counts(self.BOTTOM_HEIGHT), 0, timeoutMs=10)

        if self.set_pos is None or self.at_pos():
            self.compressor.start()
        else:
            self.compressor.stop()

    def metres_to_counts(self, metres):
        return int(metres * self.COUNTS_PER_METRE)

    def stop(self):
        """Stop the lift motor"""
        self.set_pos = None
        self.motor.stopMotor()

    def reset(self):
        self.move(self.BOTTOM_HEIGHT)

    def move(self, input_setpos):
        """Move lift to height on encoder

        Args:
            input_setpos (int): Encoder position to move lift to in m.
        """
        self.set_pos = input_setpos
        if self.set_pos - self.get_pos() < 0:
            self.motor.configMotionAcceleration(self.DOWNWARD_ACCELERATION, timeoutMs=10)
        else:
            self.motor.configMotionAcceleration(self.UPWARD_ACCELERATION, timeoutMs=10)

        self.motor.set(self.motor.ControlMode.MotionMagic, self.metres_to_counts(self.set_pos))

    @magicbot.feedback
    def get_pos(self) -> float:
        """Get the current height of the lift."""
        return self.motor.getSelectedSensorPosition(0) / self.COUNTS_PER_METRE

    @magicbot.feedback
    def get_velocity(self) -> float:
        """Get the current velocity of the lift."""
        return self.motor.getSelectedSensorVelocity(0) / self.COUNTS_PER_METRE

    def at_pos(self):
        """Finds if cube location is at setops and within threshold

        Returns:
            bool: If the encoder is at the pos
        """
        if self.set_pos is None:
            return False
        return abs(self.set_pos - self.get_pos()) < self.THRESHOLD
