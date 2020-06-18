import time
import socket
import sys
import os
import hashlib
import pickle
import ast


class FileClient:
    """
    FileClient class:
    A small self contained class that connects to a socket purely for sending a file to the server.
    Once the file has been sent the socket is closed off.
    Uses a hardcoded server and port.
    """

    def send_file(self, folder, file):
        """
        For a given file and location, a connection is opened, the file is opened and sent to the server and connection
        closed down once completed.
        :param file: The name of the file to be read
        :param folder: The location for the file read
        """
        while True:
            print('FC: Connecting to host: localhost port: 7100' + file)
            # Configure the socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('localhost', 7100))
            print('FC: Connected')
            print('FC: Reading:' + file)
            # Open the file
            f = open(os.path.join(folder, file), 'rb')
            # Send the data in chunks
            data = f.read(1024)
            while (data):
                s.sendall(data)
                data = f.read(1024)
            # Close the file
            f.close()
            print('FC: File sent')
            # Close the socket
            s.close()
            # Exit out now file send is complete
            break


class SyncClient:
    """
    SyncClient class:
    The main class, used for handling the main socket, processes any messages from the server and sends files required
    by the server.
    """

    LOCAL_FOLDER = ''
    CURRENT_FILE_LIST = ''
    SOCKET = []
    HEADER = 10
    SERVER = '192.168.0.36'
    PORT = 7101

    def __init__(self):
        """
        Initialise the main SyncClient class
        Checks arguments for 1 argument which should be the directory to monitor.
        Socket connection to the hardcoded values stored in the variables SERVER and PORT
        """
        # Find the first argument and assign to variable LOCAL_FOLDER
        for i, arg in enumerate(sys.argv):
            if i == 1:
                self.LOCAL_FOLDER = str(arg)
                print('SC: Local directory:', self.LOCAL_FOLDER)
        # If no directory specified exit out
        if self.LOCAL_FOLDER == '':
            print('SC: No local directory specified')
            sys.exit(1)

    def read_local_storage(self):
        """
        For the LOCAL_FOLDER variable set from argument passed in, traverse the directory structure beneath it and build
        a file list of every file contained beneath.

        For every file discovered a new list object is created for that file and the following data is stored.

        [<root directory of the file>, <file name including extension>, <md5 of the file>]

        We store the root directory, file name and md5 of each file in that order. The md5 is used server side in order
        to check whether we have other files that match that md5 so should a new file that needs uploading to the server
        match that md5 we can simply do a local copy and rename on the server to avoid re transmitting data we already
        have.

        In addition we also use the md5 to check if client files with the same name as a file on the server match in
        orde to indicate whether an update has occurred.

        :return file_list - List object containing a collection of list objects that are used to store file details
        described above
        """
        print('SC: Local file list')
        file_list = []
        for root, dirs, files in os.walk(self.LOCAL_FOLDER):
            for file in files:
                # Create an md5 object for the file
                file_md5 = hashlib.md5()
                # Open the file in binary format to calculate the md5
                with open(os.path.join(root, file), 'rb') as open_file:
                    # Add chunks of data to the md5 object
                    for data in iter(lambda: open_file.read(4096), b""):
                        file_md5.update(data)
                file_list.append([root, file, file_md5.hexdigest()])
                print('SC: File', [root, file, file_md5.hexdigest()])
        return file_list

    def run(self):
        """
        The main run loop of the ClientSync class that is used to monitor the socket for connections and receiving the
        data from said connection and processing the messages received and acting upon them
        """
        # Setup the socket and connect to the server
        self.SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SOCKET.connect((self.SERVER, self.PORT))
        # Find the local files and send message with list to the server
        self.send_initial_file_list_to_server()
        while True:
            # Initialise variables to indicate whether we are at the start of the message <message_start> and
            # therefore need to process the header value to find the total length of the message and <message_total>
            # is initialised in readiness for holding the full message
            message_start = True
            message_total = b''

            while True:
                # Receive the data
                data = self.SOCKET.recv(1024)
                if message_start:
                    message_length = int(data[:self.HEADER])
                    print("SC: New message received - Length:", message_length)
                    # Received the start of a message and have it's length so no longer need to set the message
                    # length until will start receiving the next message
                    message_start = False

                # Add additional data received to the existing message we are processing
                message_total += data

                # if the length of all the data recieved matches that which was specified in the header then we have
                # a complete message
                if len(message_total) - self.HEADER == message_length:
                    # The full message has now been received
                    # Load the data in using pickle
                    message_to_process = pickle.loads(message_total[self.HEADER:])
                    print('SC: RCVD:', message_to_process)

                    # Reset the flag for a new message and clear the full message as not needed from now
                    message_start = True
                    message_total = b""

                    # Load in the message type which is the first string in the message and defines what the
                    # purpose of the message is, essentially a command
                    message_type = str(message_to_process).split(':')[0]
                    # Load in the message data which is to be used by the command
                    message_data = str(message_to_process).split(':')[1]

                    if message_type == 'filerequest':
                        # A file request message has been received so process it
                        self.process_file_request_message(message_data)
                    elif message_type == 'sync':
                        # Sync done message received so break out of the loop
                        break

            # All the work is done so close down the connection and break out to the timer
            self.SOCKET.close()
            break


    def send_initial_file_list_to_server(self):
        """
        Read in the local file list and send a filelist command to the server
        """
        # Get the file list
        self.CURRENT_FILE_LIST = self.read_local_storage()
        print('SC: Local file list:')
        for local_file in self.CURRENT_FILE_LIST:
            print('SC: File ', local_file)
        # Generate the message to send to the server
        data = 'filelist:' + str(self.CURRENT_FILE_LIST)
        message = pickle.dumps(data)
        message = bytes(f"{len(message):<{self.HEADER}}", 'utf-8') + message
        print('SC: SEND:', data)
        # Send the message
        self.SOCKET.send(message)

    def process_file_request_message(self, data):
        """
        Takes in a list that conatins a single file to be sent to the server
        :param data: The file from the server
        """
        # Convert the data string into a list
        file_data = ast.literal_eval(data)
        # Extract the file name from the file list object
        file_name = file_data[0][1]
        print('SC: Sending file', file_name)
        # Wait for a bit giving the server time to open the port
        time.sleep(3)
        # Send the file data to the server
        FileClient().send_file(file_data[0][0], file_data[0][1])


if __name__ == '__main__':
    """
    In a loop run the SyncClient class run(), upon completion do it again in 60s
    """
    while True:
        SyncClient().run()
        time.sleep(60)
