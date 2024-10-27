import bluetooth
import requests
import json
import os
import socket

class BluetoothServer:
    def __init__(self):
        self.mac_address= ""
        self.data = None
        self.server_sock = None
        self.client_sock = None
        self.port_number = None

    def ConnectBluetooth(self):
        print('Initialising Server...')
        try:
            os.system("sudo hciconfig hci0 piscan")

            self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_sock.bind(self.mac_address,bluetooth.PORT_ANY)
            self.server_sock.listen(self.port_number)
            print("Server bonded to port,  listening...")

        
            self.port = self.server_sock.getsockname()[1]
            uuid = ""

            bluetooth.advertise_service(self.server_sock,"grp18racoons",service_id = uuid, 
                                        service_classes=[uuid,bluetooth.SERIAL_PORT_CLASS], 
                                        profiles = [bluetooth.SERIAL_PORT_PROFILE])
            
            print(f"waiting for connection on RFCOMM Channel {self.port}........")
            self.client_sock,self.mac_address = self.server_sock.accept()
            print(f"Accepted connection from {self.mac_address}")

        except Exception as e:
            print(f"Connection error, server shutting down Error: {e}")
            self.server_sock.close()
            self.client_sock.close()

    
    def SendToBluetooth(self,data):
        try:
            
            json_data = json.dumps(data)
            self.client_sock.send(json_data)
        except Exception as e:
            print(f"Message not send.... Error: {e}")

    def ListenFromBluetooth(self):
        try:
            message = self.client_sock.recv(1024)
            print(f"Messafe received....:{message}")
            message_processed = message.strip().decode("utf-8")
            return message_processed
        except Exception as e:
            print(f"Message not received from Android..... Error: {e}")

            
    def DisconnectBluetooth(self):
        try:
            # Shut down and reintialise serversock
            self.server_sock.shutdown(socket.SHUT_RDWR)
            self.server_sock.close()
            self.server_sock = None
            # Shut down and reintialise clientsock
            self.client_sock.shutdown(socket.SHUT_RDWR)
            self.client_sock.close()
            self.client_sock = None
            print("Bluetooth disconnected successfully")
        except Exception as e:
            print(f"Bluetooth not disconnected Error: {e}")
