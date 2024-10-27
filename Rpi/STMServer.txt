import serial
import requests

import time

class STM32:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=1):
        # Initialize the serial connection with the STM32
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.detection = {}

    def ConnectSTM32(self):
        try:
            # Open the serial connection
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"Connected to STM32 on {self.port} with baudrate {self.baudrate}")
        except serial.SerialException as e:
            print(f"Failed to connect to STM32: {e}")

     
    def SendData(self, data):
        print(f"Sending data to STM32.....")
        if self.serial_connection:
            if isinstance(data, str):
                data = data.encode("utf-8") 
            self.serial_connection.write(data)
            print(f"Sent data: {data}")
        else:
            print("Serial connection not established.")

    def ReadData(self):
        print(f"Reading Data from STM...")
        if self.serial_connection:
            try:
                while True: 
                    received_data = self.serial_connection.readline().decode().strip()
                    print(f"Received data: {received_data}")
                    return received_data
                    
            except serial.SerialException as e:
                print(f"Error reading data: {e}")
                return None
        else:
            print("Serial connection not established.")
            return None

    def CheckACK(self, command):
        print(f"Waiting for ACK for command: {command}")
        while True:
            response = self.ReadData()
            if response and "ACK" in response:
                print(f"ACK received for command: {command}")
                return True
            else:
                print(f"No ACK yet for command: {command}, retrying...")
                print(response)
            time.sleep(1)  
    

    def DisconnectSTM(self):
        print(f"Shutting down STMServer.....")
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            self.serial_connection = None
            print("Serial connection closed.")
        else:
            print("Disconnect Failed....")