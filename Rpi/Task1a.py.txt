from BluetoothServer import BluetoothServer
from STMServer import STMServer
import json
import queue
import os
import requests
from multiprocessing import Process, Manager
import picamera
import time
## Task 1a


class RPI:
    def __init__(self):
        print(f"Initialising Rpi......")
        self.android = BluetoothServer()
        self.stm32 = STMServer()
        self.manager = Manager()

        # Initialise Queue for multiproccessing
        self.android_queue = self.manager.Queue() #Send info to android
        self.command_queue = self.manager.Queue()
        self.path_queue = self.manager.Queue()
        self.rpi_queue = self.manager.Queue() # Handle SNAP command to CV API
        self.algo_queue = self.manager.Queue()


        # Prevent Race Condition in RPI
        self.movement_lock = self.manager.Lock()
        self.android_dc = self.manager.Event()
        self.unpause = self.manager.Event()

        # Algo and CV Server URL 
        self.AlgoAPI = "http://192.168.18.247:4000/path"
        self.CVImageAPI = "http://192.168.18.2:5000/upload_image"
        
        # Declare Image Path
        self.image_path='/home/pi/MDP18/Task1a/image.jpg'

        # Define Process Names
        self.AndroidReceiver = None
        self.AndroidSender = None
        self.STMReceiver = None
        self.Commander = None
        self.Rpiaction = None
        self.Requestalgo = None

        # Flag
        self.current_loc = self.manager.dict()
        self.obstacle = self.manager.dict()
        self.ack_counter = 0

       
    def Start(self):
        try:
            #Start up server
            self.android.ConnectBluetooth()
            self.stm32.ConnectSTM32()

            # Create Proccesses
            self.AndroidReceiver = Process(target=self.ListenAndroid)
            self.AndroidSender = Process(target=self.SendAndroid)
            self.STMReceiver = Process(target=self.ListenSTM)
            self.Commander = Process(target=self.DoCommand)
            self.Rpiaction = Process(target=self.RPIAction)
            self.Requestalgo= Process(target=self.RequestAlgo)
        

            # Start Process
            self.AndroidReceiver.start()
            self.AndroidSender.start()
            self.STMReceiver.start()
            self.Commander.start()
            self.Rpiaction.start()
            self.Requestalgo.start()
         

            self.ReconnectAndroid()
        except KeyboardInterrupt:
            self.Stop()
            
    def RequestAlgo(self):
        while True:
            print("REQ RUNNING")
            try:
                data = self.algo_queue.get()
                print(f"data received :{data}")
                    
                try:
                    url = self.AlgoAPI
                    response = requests.post(url, json=data)
                    print("Attempting to connect to Algo")
                    if response.status_code == 200:
                        try:
                            api_response = response.json()  # Try to parse JSON response
                            print(f"API Response: {api_response}")
                            command_response = api_response['data']['commands']
                            path_response = api_response['data']['path']
                            for path in path_response[1:]:
                                self.path_queue.put(path)
                            
                            for command in command_response:
                                self.command_queue.put(command)
                            print("Command inserted to queue")
                        except ValueError:
                            print("Failed to parse JSON from API response.")
                    else:
                        print(f"API request failed with status code: {response.status_code}")   
                except Exception as e:
                    print(f"Error sending to API: {e}")                
            except queue.Empty: 
                print("Empty Queue")

    def ListenAndroid(self):
        while True:
            print("lIsteing and")
            try: 
                message = self.android.ListenFromBluetooth()
                print(message)
            except Exception as e:
                print(f"failed to listen to android Error: {e}")

            if message == None:
                continue
            
            json_data = json.loads(message)
            if json_data['cat'] == "arenaInfo":
                input_data = {
                                "obstacles": json_data['value']['obstacles'],
                                "retrying": False,
                                "robot_x": json_data['robot_x'],
                                "robot_y": json_data['robot_y'],
                                "robot_dir": json_data['robot_dir']
                            }
                self.obstacle['obstacles'] = json_data['value']['obstacles']
                print(self.obstacle)
                self.algo_queue.put(input_data)
                print(f"Placed in algo queue {input_data}")
            elif json_data["cat"] ==  "control":
                if json_data["value"]=="start":
                    if not self.command_queue.empty():
                        #self.stm32.SendData("RST0")
                        self.unpause.set()
                        print("Start command Received BT -> RPI")
                        self.android_queue.put({"cat":"INFO","value":"driving"})
                        self.android_queue.put({"cat":"STATUS","value":"RUNNING"})
                    else:
                        print("Command Queue is Empty")

    def SendAndroid(self):
        while True:
            try:
                message = self.android_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                print(f"Sending to android : {message}")
                self.android.SendToBluetooth(message)
            except OSError:
                self.android_dc.set()
                print("Android Disconnected")

    def ReconnectAndroid(self):
        while True:
            self.android_dc.wait()

            print("Android Down")
            # Kill related process
            self.AndroidReceiver.kill()
            self.AndroidSender.kill()

            #wait for all process to end
            self.AndroidReceiver.join()
            self.AndroidSender.join()

            assert self.AndroidSender.is_alive() is False
            assert self.AndroidReceiver.is_alive() is False
            print("All Process are killed")  

            self.android.DisconnectBluetooth()
            self.android.ConnectBluetooth()

            self.AndroidReceiver = Process(target=self.ListenAndroid)
            self.AndroidSender = Process(target=self.SendAndroid)

            self.AndroidReceiver.start()
            self.AndroidSender.start()
            print("You are connected")
            
            self.android_queue.put({"cat":"INFO",
                                    "value":"You are reconnected"})
            self.android_queue.put({"cat":"mode","value":"path"})
            self.android_dc.clear()


    
    def ListenSTM(self):
        while True:
            
            message = self.stm32.ReadData()
            if message.startswith("ACK") or "ACK" in message:
                self.ack_counter+= 1
                if self.ack_counter == 2:
                    try:
                        self.movement_lock.release()
                        print(" ACK received.....Release Lock")
                    
                        cur_location = self.path_queue.get_nowait()

                        self.current_loc['x'] = cur_location['x']
                        self.current_loc['y'] = cur_location['y']
                        self.current_loc['d'] = cur_location['d']
                        
                        print(f"Curr Loc : {self.current_loc}")
                        json_path = {"cat": "LOCATION",
                                        "value": {"x": cur_location['x'],
                                                  "y": cur_location['y'],
                                                  "d": cur_location['d']}}
                        self.android_queue.put(json_path)
                        self.ack_counter = 0
                       
                    except Exception as e:
                        print("Error, tried to release lock")

            else:
                pass
                #print(f"STM Do not Recognise Message: {message}")

    def Stop(self):
        self.android.DisconnectBluetooth()
        self.stm32.DisconnectSTM()
        print("Program ended...")

    def DoCommand(self):
        while True:
            command = self.command_queue.get()
            try:
                self.retrylock.acquire()
                self.retrylock.release()
            except:
                self.unpause.wait() 
            self.movement_lock.acquire()

            stm32_prefixes = ("FS", "BS", "FW", "BW", "FL", "FR", "BL",
                              "BR", "TL", "TR", "A", "C", "DT", "STOP", "ZZ", "RS")
            if command.startswith(stm32_prefixes):
                self.stm32.SendData(command)
                print(f"Sending to STM32: {command}")

            elif command.startswith("SNAP"):
                obstacle_id_with_signal = command.replace("SNAP", "")
                self.rpi_queue.put({"cat":"SNAP", 
                                    "value":f"{obstacle_id_with_signal}"})
                
            elif command == "FIN":
                time.sleep(1)
                print("Finished Algo")
                if not self.obstacle:
                    self.android_queue.put({"cat":"STATUS","value":"FINISHED"})
                    self.unpause.clear()
                    self.movement_lock.release()
                else:
                    self.unpause.clear()
                    self.movement_lock.release()
                    input_data = {
                                "obstacles": self.obstacle,
                                "retrying": True,
                                "robot_x": self.current_loc['x'],
                                "robot_y": self.current_loc['y'],
                                "robot_dir": self.current_loc['d']
                    }
                    self.algo_queue.put(input_data)
                    if not self.command_queue.empty():
                        #self.stm32.SendData("RST0")
                        self.unpause.set()
                        print("Start command Received BT -> RPI")
                        self.android_queue.put({"cat":"INFO","value":"driving"})
                        self.android_queue.put({"cat":"STATUS","value":"RUNNING"})
                    else:
                        print("Command Queue is Empty")
                    
            else:
                raise Exception(f"Unknown Command: {command}")
                    

    def RPIAction(self):
        while True:
            action = self.rpi_queue.get()
            print(f"Recieved Action: {action}")

            if action["cat"] == "SNAP":
                self.SnapandReceive(action["value"])

    def SnapandReceive(self,obstacleIDwithsignal):
        camera = picamera.PiCamera()
        camera.start_preview()
        time.sleep(1)
        detections = []
        for i in range(3):        
            camera.capture(self.image_path)

            with open(self.image_path,'rb') as img_file:
                files = {'file':img_file}
                
            
                try:
                    response = requests.post(self.CVImageAPI,files=files)
                    if response.status_code == 200:
                        detection_response = response.json()
                        detections = detection_response.get('detections',[])
                        
                        if len(detections)>0:
                            print(f"Detections found: {detections}")
                            self.movement_lock.release()
                            break
                        else:
                            print(f"No objects detected in attempt {i+1}. Retrying..")
                    else:
                        print(f"Failed to send image: {response.status_code}")
                except Exception as e:
                    print(f"Error in sending message {e}")
                
        try:
            if len(detections)>0:
                imageId = detections[0]["ImageID"]
                obstacleID = obstacleIDwithsignal[0]
                self.android_queue.put({"cat":"IMAGE-REC",
                                    "value":{"obstacle_id":obstacleID,"image_id":imageId}})
                
                del self.obstacle[obstacleID-1]
                print(self.obstacle)
            else:
                self.movement_lock.release()
            

        except Exception as e:
            print(f"Object not detected Error:{e}")
        finally:
            camera.stop_preview()
            camera.close()
        
    
    
                
            
            



    def ClearQueue(self):
        while not self.command_queue.empty():
            self.command_queue.get()
        while not self.path_queue.empty():
            self.path_queue.get()
        print("Queue Cleared")



if __name__ == "__main__":
    task1 = RPI()
    task1.Start()
    









