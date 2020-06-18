import socket
import sys
import os
import hashlib
import pickle
import shutil
import ast


class FileServer:
    """
    FileServer class:
    A small self contained class that creates a independent socket purely for receiving a file sent from a client
    connection.
    Once the file has been received the socket is closed off.
    Uses a hardcoded server and port.
    """

    def receive_file(self, file, folder):
        """
        For a given file and location, a connection is opened, the file is opened in readiness for incoming data,
        upon data received it is written to the file. Once all the data is received the file in closed and connection
        closed down from the client.
        :param file: The name of the file to be written to
        :param folder: The location for the file being written
        """
        print('FS: Opening sever: localhost port: 7100')
        # Configure the socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 7100))
        s.listen(5)
        print('FS: Waiting for connection')
        client, address = s.accept()
        # Open the give file in preparation for data
        print('FS: Connect to: ', address)
        with open(os.path.join(folder, file), 'wb') as f:
            while True:
                data = client.recv(1024)
                if not data:
                    break
                f.write(data)
        # Close the file once data has been received
        f.close()
        print('FS: File saved:', file)
        # Close the client connection
        client.close()
        print('FS: Closed')


class SyncServer:
    """
    SyncServer Class:
    The main class, used for handling the main socket, processes any messages from a client and updates the local
    storage to be in line with that specified by the client
    """

    LOCAL_FOLDER = ''
    CURRENT_FILE_LIST = ''
    SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    REQUEST_FILE_LIST = []
    HEADER = 10
    SERVER = 'localhost'
    PORT = 7101

    def __init__(self):
        """
        Initialise the main SyncServer class
        Checks arguments for 1 argument which should be the directory to maintain against data provided by client
        Binds the socket connection to the hardcoded values stored in the variables SERVER and PORT
        """
        # Find the first argument and assign to variable LOCAL_FOLDER
        for i, arg in enumerate(sys.argv):
            if i == 1:
                self.LOCAL_FOLDER = str(arg)
                print('SS: Local directory:', self.LOCAL_FOLDER)
        # If no directory specified exit out
        if self.LOCAL_FOLDER == '':
            print('SS: No local directory specified')
            sys.exit(1)
        # Bind the socket to the server and port provided and set listen queue
        print('SS: Socket bind:', (self.SERVER, self.PORT))
        self.SOCKET.bind((self.SERVER, self.PORT))
        self.SOCKET.listen(10)

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
        print('SS: Local file list')
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
                print('SS: File', [root, file, file_md5.hexdigest()])
        return file_list

    def run(self):
        """
        The main run loop of the ServerSync class that is used to monitor the socket for connections and receiving the
        data from said connection and processing the messages received and acting upon them
        """
        while True:
            # Read in the current file list on server
            self.CURRENT_FILE_LIST = self.read_local_storage()
            # Allow the socket to receive connections
            client, address = self.SOCKET.accept()
            print('SS: Connection:', address)

            # Initialise variables to indicate whether we are at the start of the message <message_start> and
            # therefore need to process the header value to find the total length of the message and <message_total>
            # is initialised in readiness for holding the full message
            message_start = True
            message_total = b""

            while True:
                # Receive the data
                data = client.recv(1024)
                if data != b"":
                    if message_start:
                        message_length = int(data[:self.HEADER])
                        print("SS: New message received - Length:", message_length)
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
                        print('SS: RCVD:', message_to_process)

                        # Reset the flag for a new message and clear the full message as not needed from now
                        message_start = True
                        message_total = b""

                        # Load in the message type which is the first string in the message and defines what the
                        # purpose of the message is, essentially a command
                        message_type = str(message_to_process).split(':')[0]
                        # Load in the message data which is to be used by the command
                        message_data = str(message_to_process).split(':')[1]

                        if message_type == 'filelist':
                            # A filelist message has been received, this gives details of the clients current file list
                            # which can tthen be used for comparison against the servers file list
                            self.process_file_list_message(message_data)

                            # Check whether there are any files that need requesting from the client
                            if self.REQUEST_FILE_LIST != []:
                                for req_file in self.REQUEST_FILE_LIST:
                                    # For each file generate a filerequest message to send to client and initiate the
                                    # FileServer class to receive the file data
                                    data = 'filerequest:' + str([req_file])
                                    print('SS: SEND:', data)
                                    message = pickle.dumps(data)
                                    message = bytes(f"{len(message):<{self.HEADER}}", 'utf-8') + message
                                    client.send(message)
                                    FileServer().receive_file(req_file[1], self.LOCAL_FOLDER)

                            # Finished processing the files to request from the client, so clear out the request list
                            self.REQUEST_FILE_LIST = []
                            # Send a sync:done message to the client to close down the current dialogue with the client
                            data = 'sync:done'
                            print('SS: SEND:', data)
                            message = pickle.dumps(data)
                            message = bytes(f"{len(message):<{self.HEADER}}", 'utf-8') + message
                            client.send(message)

                            # Shutdown the current client connection
                            client.shutdown(socket.SHUT_RDWR)
                            # Break out of the current loop and wait for next connection from client
                            break

    def process_file_list_message(self, data):
        """
        Take in the data from the filelist message which is a string, convert it into a list, print the details and
        go on to compare the list with the servers file list
        :param data: message data received from the filelist message
        """
        # Load the message data into a list object (converts string to list)
        file_list = ast.literal_eval(data)
        print('SS: Client file list')
        for file in file_list:
            print('SS: File', file)
        # Compare the client file list with the server file list
        self.compare_client_files_with_local(file_list)

    def compare_client_files_with_local(self, files):
        """
        Take the file list from the client and compare against the file list the server current has.
        Find any missing files (by file name)
        Find any deletable files (by file name)
        Find any to update (if the file name matches but not the md5)
        Find any files that are missing on the server but there is already a file on the server with matching md5
        so we can copy that file locally and rename it to avoid transferring unnecessary data
        :param files: The client file list to process
        """
        # Initialise the list to store lists of file with different files requiring actions
        files_to_get = []
        files_to_delete = []
        files_to_duplicate = []

        # Check for files to add or update or copy/rename locally, working through the list of files from the client
        # first
        for client_file in files:
            found = False
            # For the file from the client, go through each server file and see if we have a match
            for server_file in self.CURRENT_FILE_LIST:
                if client_file[1] == server_file[1]:
                    # Found a matching file on the server with name
                    found = True
                    # Check the md5 for the file so see if they differ
                    if client_file[2] != server_file[2]:
                        # The md5 do not match for the two files so need a new copy from the client
                        # Delete the server copy of the file
                        files_to_delete.append(server_file)
                        # Request a new copy from the client
                        files_to_get.append(client_file)
                    # We found a match in the server file list so break out to avoid going through entire server files
                    break

            # If a matching file has not been found in the server list check through server list for a file with
            # match md5 which can be copied and renamed locally, if this can't be done then request file from the client
            if not found:
                for file in self.CURRENT_FILE_LIST:
                    found = False
                    # Check for matching md5 of client file locally
                    if client_file[2] == file[2]:
                        # Found a file with matching md5 so can be copied/renamed locally
                        files_to_duplicate.append([file[1], client_file[1]])
                        found = True
                        break
                # If no matching file found on server by md5 then request file from client
                if not found:
                    files_to_get.append(client_file)

        # Go through each file on the server and find match in client list, if not found then the server file needs to
        # be deleted
        for server_file in self.CURRENT_FILE_LIST:
            found = False
            for client_file in files:
                if client_file[1] == server_file[1]:
                    # Found a client file that matches the server so keep the file
                    found = True
                    break
            if not found:
                # No match found on the client so we can delete the server file
                files_to_delete.append(server_file)
        # Perform the updates on the server file system
        self.update(files_to_get, files_to_delete, files_to_duplicate)

    def update(self, get_files, delete_files, copy_rename_files):
        """
        Update the file system on the server, firstly we perform the copy and rename of files local to the server.
        This step is performed first in case the file we are copying is due to be deleted in a later step.
        Then any files that are no longer needed are deleted.
        Finally the global REQUEST_FILE_LIST is updated with any files the server needs from the client, which is used
        in run() to send requests
        :param get_files: List of files to request from the client
        :param delete_files: List of files to delete from the server
        :param copy_rename_files: List of files to locally copy and rename on the server
        """
        # Copy and rename any files the server has locally
        for file in copy_rename_files:
            print('SS: Copying file: ' + file[0] + ' and renaming to ' + file[1])
            shutil.copy(os.path.join(self.LOCAL_FOLDER, file[0]), os.path.join(self.LOCAL_FOLDER, file[1]))

        # Delete any files no longer present on client
        for file in delete_files:
            print('SS: Deleting file:', file)
            os.remove(os.path.join(file[0], file[1]))

        # Update the global REQUEST_FILE_LIST with files required from client
        self.REQUEST_FILE_LIST = get_files


if __name__ == '__main__':
    SyncServer().run()
