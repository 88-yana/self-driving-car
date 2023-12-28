import Adafruit_PCA9685
import time  #timeというモジュールを使用する
import RPi.GPIO as GPIO #ラズパイのGPIOピンを操作するためのモジュール
from datetime import datetime #日時を取得するためのモジュール
import os #ファイル操作のためのモジュール
import signal
import sys
import csv

# pin number
SPEED = 13
SERVO = 14

# 前進最高速、停止、後進最高速のPWM値
# pwm.set_pwm(SPEED_CNTL, 0, 380)
# MAX = 350
# MIN = 369
PWM_FORWARD_MAX = 363
PWM_FORWARD_MID = 365
PWM_FORWARD_MIN = 365
PWM_STOP        = 380
PWM_BACK        = 395

# 左いっぱい、まっすぐ、右いっぱいのPWM値
# pwm.set_pwm(SERVO, 0, 380)
PWM_LEFT     = 290
PWM_STRAIGHT = 340
PWM_RIGHT    = 390

# array index
FRONT_SENSOR = 0
LEFT_SENSOR  = 1
RIGHT_SENSOR = 2

trig_arr = [15,13,32] #Trigピン番号(正面、左、右)
echo_arr = [26,24,31] #Echoピン番号(正面、左、右)

LR_DIFF = 20

pwm = Adafruit_PCA9685.PCA9685(address=0x40)
pwm.set_pwm_freq(60)

# GPIOピン番号の指示方法
GPIO.setmode(GPIO.BOARD)
#超音波センサ初期設定
for i in range(len(trig_arr)):
    GPIO.setup(trig_arr[i],GPIO.OUT,initial=GPIO.LOW)
    GPIO.setup(echo_arr[i],GPIO.IN)

pwm.set_pwm(SERVO, 0, PWM_STRAIGHT)
pwm.set_pwm(SPEED, 0, PWM_STOP)

sig = 0
sig_flag = 0

def sigint_handler(signum, frame):
    global sig
    pwm.set_pwm(SERVO, 0, PWM_STRAIGHT)
    # タイヤを停止させる
    pwm.set_pwm(SPEED, 0, PWM_STOP)
    while True:
        time.sleep(1)
        if sig == 1:
            break
    sig = 0

def sigquit_handler(signum, frame):
    global sig
    global sig_flag
    sig = 1
    sig_flag = 1

def sigill_handler(signum, frame):
    pwm.set_pwm(SERVO, 0, PWM_STRAIGHT)
    # タイヤを停止させる
    pwm.set_pwm(SPEED, 0, PWM_STOP)
    csv_file_path = "q_table.csv"
    with open(csv_file_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        
        # ヘッダーを書き込む（状態と行動の組み合わせを列に持つ）
        header = ["State"] + actions
        writer.writerow(header)
        
        # Qテーブルの内容を書き込む
        for i, state in enumerate(states):
            row = [str(state)] + [str(q) for q in q_table[i]]
            writer.writerow(row)
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGQUIT, sigquit_handler)
signal.signal(signal.SIGILL, sigill_handler)

import numpy as np

# 状態空間の定義 (超音波センサーの距離)
states = [(d1, d2, d3) for d1 in range(11) for d2 in range(11) for d3 in range(11)]
state_index = {state: i for i, state in enumerate(states)}

# 行動空間の定義 (前進、左折、右折)
actions = ["Forward", "Left", "Right"]
action_index = {action: i for i, action in enumerate(actions)}

csv_file_path = "q_table.csv"
try:
    with open(csv_file_path, 'r') as csv_file:
        reader = csv.reader(csv_file)
        
        # ヘッダーをスキップ
        header = next(reader)
        
        # 状態と行動に関連するQ値を読み込む
        states = []
        q_table = []
        for row in reader:
            states.append(eval(row[0]))  # evalを使って文字列をPythonオブジェクトに変換
            q_table.append([float(q) for q in row[1:]])
        states = np.array(states)
        q_table = np.array(q_table)
except FileNotFoundError:
    # ファイルが存在しない場合は全てのQ値を0で初期化
    q_table = np.zeros((len(states), len(actions)))

# 読み込んだデータをnumpy arrayに変換

# パラメータの設定
learning_rate = 0.1
discount_factor = 0.9
exploration_rate = 0.1
epochs = 1000

def Measure(trig, echo):
    sigon  = 0 #Echoピンの電圧が0V→3.3Vに変わった時間を記録する変数
    sigoff = 0 #Echoピンの電圧が3.3V→0Vに変わった時間を記録する変数
    GPIO.output(trig,GPIO.HIGH) #Trigピンの電圧をHIGH(3.3V)にする
    time.sleep(0.00001) #10μs待つ
    GPIO.output(trig,GPIO.LOW) #Trigピンの電圧をLOW(0V)にする
    while(GPIO.input(echo) == GPIO.LOW):
        sigon = time.time() #Echoピンの電圧がHIGH(3.3V)になるまで、sigonを更新
    while(GPIO.input(echo) == GPIO.HIGH):
        sigoff = time.time() #Echoピンの電圧がLOW(0V)になるまで、sigoffを更新
    distance = (sigoff - sigon)*34000/2 #距離を計算(単位はcm)
    if 200 < distance:
        distance = 200 #距離が200cm以上の場合は200cmを返す
    return int(distance / 20)

def get_state():
    time.sleep(0.1)
    d_fr = Measure(trig_arr[FRONT_SENSOR],echo_arr[FRONT_SENSOR])
    d_lh = Measure(trig_arr[LEFT_SENSOR],echo_arr[LEFT_SENSOR])
    d_rh = Measure(trig_arr[RIGHT_SENSOR],echo_arr[RIGHT_SENSOR])
    state = (d_fr, d_lh, d_rh)
    return state

def get_reward(state, next_state, action):
    if next_state[0] <= 1:
        return -10
    elif next_state[1] < 3 and next_state[1] < state[1]:
        return -5
    elif next_state[2] < 2 and next_state[2] < state[2]:
        return -5
    elif action == "Forward":
        return 3
    elif action == "Right":
        return 2
    elif action == "Left":
        return 1
    

# シミュレーション上での報酬と次の状態
def simulate_environment(state, action):
    if (action == "Forward"):
        pwm.set_pwm(SERVO, 0, PWM_STRAIGHT)
        pwm.set_pwm(SPEED, 0, PWM_FORWARD_MID)
    elif (action == "Right"):
        pwm.set_pwm(SERVO, 0, PWM_RIGHT)
        pwm.set_pwm(SPEED, 0, PWM_FORWARD_MIN)
    elif (action == "Left"):
        pwm.set_pwm(SERVO, 0, PWM_LEFT)
        pwm.set_pwm(SPEED, 0, PWM_FORWARD_MIN)
    next_state = get_state()
    reward = get_reward(state, next_state, action)
    return reward, next_state

while True:
    time.sleep(1)
    if sig_flag == 1:
        sig_flag = 0
        sig = 0
        break
d_fr = Measure(trig_arr[FRONT_SENSOR],echo_arr[FRONT_SENSOR])
d_lh = Measure(trig_arr[LEFT_SENSOR],echo_arr[LEFT_SENSOR])
d_rh = Measure(trig_arr[RIGHT_SENSOR],echo_arr[RIGHT_SENSOR])
state = (d_fr, d_lh, d_rh)

while True:
    action = actions[np.argmax(q_table[state_index[state]])]

    reward, next_state = simulate_environment(state, action)

    # Q値の更新
    if (sig_flag == 1):
        sig_flag = 0
        state = (d_fr, d_lh, d_rh)
        continue
    q_table[state_index[state], action_index[action]] = \
        (1 - learning_rate) * q_table[state_index[state], action_index[action]] + \
        learning_rate * (reward + discount_factor * np.max(q_table[state_index[next_state]]))

    state = next_state

#超音波センサーで距離を測る関数

# while True:  #以下の部分をずっと繰り返す
#     d_fr = Measure(trig_arr[FRONT_SENSOR],echo_arr[FRONT_SENSOR])

#     d_lh = Measure(trig_arr[LEFT_SENSOR],echo_arr[LEFT_SENSOR])
 
#     d_rh = Measure(trig_arr[RIGHT_SENSOR],echo_arr[RIGHT_SENSOR])
    
#     Cntl(d_fr, d_lh, d_rh)
#     time.sleep(0.01)

# csv_file_path = "q_table.csv"
# with open(csv_file_path, 'r') as csv_file:
#     reader = csv.reader(csv_file)
    
#     # ヘッダーをスキップ
#     header = next(reader)
    
#     # 状態と行動に関連するQ値を読み込む
#     states = []
#     q_table = []
#     for row in reader:
#         states.append(eval(row[0]))  # evalを使って文字列をPythonオブジェクトに変換
#         q_table.append([float(q) for q in row[1:]])

# # 読み込んだデータをnumpy arrayに変換
# states = np.array(states)
# q_table = np.array(q_table)

# # 学習後、Qテーブルを使用して運転
# while True:
#     action = actions[np.argmax(q_table[state_index[current_state]])]
#     print(f"Taking action: {action}")
    
#     # センサーデータを取得して次の状態を決定する
#     # この例ではランダムな次の状態を仮定
#     next_state = np.random.choice(states)
    
#     if is_terminal_state(next_state):
#         break

#     current_state = next_state
