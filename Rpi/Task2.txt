import BluetoothServer
import STMServer
import requests
import json
import time
from multiprocessing import Process, Manager
import picamera


class RPI:
    def __init__(self):
        print("Initializing Rpi for Task 2...")
        self.android = BluetoothServer()
        self.stm32 = STMServer()
        self.manager = Manager()

        # Initialize Queues for multiprocessing
        self.android_queue = self.manager.Queue()  # Send info to Android
        self.command_queue = self.manager.Queue()
        self.rpi_queue = self.manager.Queue()  # Handle SNAP command to CV API

        # Lock and Event Setup
        self.movement_lock = self.manager.Lock()
        self.android_dc = self.manager.Event()
        self.unpause = self.manager.Event()

        # API URLs and Image Paths
        self.CVImageAPI = "http://192.168.18.3:5000/upload_image"
        self.image_path = '/home/pi/MDP18/ImageRec/Photo Taken/image.jpg'
        self.return_path = '/home/pi/MDP18/ImageRec/Result'

        self.image_path='/home/pi/MDP18/ImageRec/Photo Taken/image.jpg'
        self.return_path = '/home/pi/MDP18/ImageRec/Result'

        # Process Placeholders
        self.AndroidReceiver = None
        self.AndroidSender = None
        self.STMReceiver = None
        self.Commander = None
        self.RpiAction = None

        # Flags and other attributes
        self.current_loc = self.manager.dict()

    def Start(self):
        try:
            # Connect to Bluetooth and STM32
            self.android.ConnectBluetooth()
            self.stm32.ConnectSTM32()

            # Create Processes
            self.AndroidReceiver = Process(target=self.ListenAndroid)
            self.STMReceiver = Process(target=self.ListenSTM)

            # Start Processes
            self.AndroidReceiver.start()
            self.STMReceiver.start()

            self.reconnect_android()

            # Handle Android Reconnection
            
        except KeyboardInterrupt:
            self.Stop()


    def ListenAndroid(self):
        """Listen for start command from Android and initialize task."""
        while True:
            print("listening android")
            try:
                message = self.android.ListenFromBluetooth()
                if message is None:
                    continue
                json_data = json.loads(message)
                
                if json_data["cat"] == "task2" and json_data["value"] == "start":
                    # Directly send the "WN" start signal to STM32
                    self.stm32.SendData("WX")
                    print("Start command received, sent 'WN' to STM32, waiting for ACK.")
                    self.unpause.set()  # Ready to start listening for STM32 ACK
            except Exception as e:
                print(f"Failed to listen to Android: {e}")

    def ListenSTM(self):
        """Wait for ACK from STM32 and then capture image and send direction command."""
        while True:
            self.unpause.wait()  # Ensure that task begins after Android start command
            ack = self.stm32.ReadData()
            if ack and "ACK" in ack:
                print("ACK received from STM32, capturing image.")
                
                # Capture image and determine direction
                direction_label = self.snap_and_recognize_image()
                
                # Based on image, decide the direction and directly send to STM32
                if direction_label == '39':  # Example: left arrow detected
                    self.stm32.SendData("LEFT")
                    print("Sent 'LEFT' to STM32.")
                elif direction_label == '38':  # Default or right arrow
                    self.stm32.SendData("RIGHT")
                    print("Sent 'RIGHT' to STM32.")
                
                # After navigating the obstacle, wait for the next ACK
                print("Waiting for next ACK for subsequent obstacle.")

    def snap_and_recognize_image(self):
        camera = picamera.Picamera()
        camera.start_preview()
        time.sleep(1)
        while True:        
            camera.capture(self.image_path)

            with open(self.image_path,'rb') as img_file:
                files = {'file':img_file}
                response = requests.post(self.CVImageAPI,files=files)
        
            if response.status_code==200:
                #Saved as bounding box
                boxed_image_path = 'boxed_image.jpg'
                with open(f'Result/{boxed_image_path}','wb') as f:
                    f.write(response.content)
            
                print(f"Image with detections saved to {boxed_image_path}")
                self.movement_lock.release()
                break
            else:
                print(f"Failed to send image: {response.status_code},{response.text}")

        detections_response=requests.get(self.CVDetectionAPI)
        if detections_response.status_code == 200:
            detections_response = detections_response.json()
            print("Detections:",detections_response)
        try:
            imageId = detections_response["ImageID"]
            return imageId
        except Exception as e:
            print(f"Object not detected Error:{e}")
        finally:
            camera.stop_preview()
            camera.close()
            

    def reconnect_android(self):
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
            #self.AndroidSender = Process(target=self.SendAndroid)

            self.AndroidReceiver.start()
            self.AndroidSender.start()
            print("You are connected")
            
            self.android_queue.put({"cat":"INFO",
                                    "value":"You are reconnected"})
            self.android_queue.put({"cat":"mode","value":"path"})
            self.android_dc.clear()

    def Stop(self):
        self.android.end_connection()
        self.stm32.disconnect()
        print("All connections closed, task stopped.")

if __name__ == "__main__":
    task2 = RPI()
    task2.Start()
