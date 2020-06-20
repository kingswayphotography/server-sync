import subprocess
import unittest
import time
import logging
import hashlib
import os
import shutil

logging.basicConfig(filename='test_sync.log',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%d-%b-%y %H:%M:%S',
                    level=logging.INFO
                    )


class ServerSyncTest(unittest.TestCase):

    CLIENT_FOLDER = '/path/to/client/folder'
    SERVER_FOLDER = '/path/to/server/folder'
    CLIENT_CYCLE = 60

    def read_storage(self, directory):
        """
        For the specified directory variable set from argument passed in, traverse the directory structure beneath it
        and build a file list of every file contained beneath.

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
        file_list = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_list.append([root, file, self.get_file_md5(root, file)])
        return file_list

    def get_file_md5(self, root, file):
        """
        For a given file, open it and read the bytes into an md5 object and then return the md5.

        :param root: The location of the file
        :param file: The file to read
        :return: md5 of the file
        """
        # Create an md5 object for the client file
        file_md5 = hashlib.md5()
        # Open the file in binary format to calculate the md5
        with open(os.path.join(root, file), 'rb') as open_file:
            # Add chunks of data to the md5 object
            for data in iter(lambda: open_file.read(4096), b""):
                file_md5.update(data)
        return file_md5.hexdigest()

    def test_001_client_file_add(self):
        """
        Add a file to the client directory and check the file arrives in the server directory.

        First the server process is started.
        test001.txt is written into the client directory in preparation for running the client.
        The client process is then started.
        Time is given to allow the transaction to take place.
        Both the client and server process are closed down.
        The server directory is inspected to see if test001.txt is present.
        """
        logging.info('START - test_001_client_file_add')
        logging.info('Starting the server process')
        with open('test_001_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Writing test001.txt into the client directory')
        with open(os.path.join(self.CLIENT_FOLDER, 'test001.txt'), 'w') as test_file:
            test_file.write('test_001_client_file_add')

        logging.info('Starting the client process')
        with open('test_001_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test001.txt is present
        for file in server_files:
            if file[1] == 'test001.txt':
                found = True
                break
        if found:
            logging.info('test001.txt has been found in the server directory')
        else:
            logging.error('test001.txt has not been found in the server directory')

        # Evaluate the result
        self.assertTrue(found, 'Failed to find the test001.txt so sync failed')
        logging.info('END - test_001_client_file_add')

    def test_002_client_file_delete(self):
        """
        Delete a file from the client directory and check it is removed from the server directory.

        First the server process is started.
        test002.txt is written into the client directory in preparation for running the client.
        The client process is then started.
        Time is given to allow the transaction to take place.
        Check the file is present in the server directory (in order to validate its deletion)
        Delete the test002.txt from the client directory.
        Wait for the client loop to go round again to perform sync.
        Both the client and server process are closed down.
        The server directory is inspected to see if test002.txt is present.
        """
        logging.info('START - test_002_client_file_delete')
        logging.info('Starting the server process')
        with open('test_002_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Writing test002.txt into the client directory')
        with open(os.path.join(self.CLIENT_FOLDER, 'test002.txt'), 'w') as test_file:
            test_file.write('test_002_client_file_delete')

        logging.info('Starting the client process')
        with open('test_002_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test002.txt is present
        for file in server_files:
            if file[1] == 'test002.txt':
                found = True
                break
        if found:
            logging.info('test002.txt has been found in the server directory so test can proceed')
        else:
            logging.error('test002.txt has not been found in the server directory so test cannot proceed')
            self.assertTrue(False, 'test002.txt has not been found in the server directory so test cannot proceed')

        logging.info('Deleting test002.txt from the client directory')
        os.remove(os.path.join(self.CLIENT_FOLDER, 'test002.txt'))

        logging.info('Waiting for the client cycle to happen')
        time.sleep(self.CLIENT_CYCLE)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test001.txt is present
        for file in server_files:
            if file[1] == 'test002.txt':
                found = True
                break
        if found:
            logging.error('test002.txt has been found in the server directory so server failed to delete')
        else:
            logging.info('test002.txt has not been found in the server directory')

        # Evaluate the result
        self.assertFalse(found, 'Found the test002.txt so sync failed')
        logging.info('END - test_002_client_file_add')

    def test_003_client_file_rename(self):
        """
        Rename a file in the client directory and check that the server does a local copy and rename.

        First the server process is started.
        test003a.txt is written into the client directory in preparation for running the client.
        The client process is then started.
        Time is given to allow the transaction to take place.
        The server directory is inspected to see if test003a.txt is present.
        test003a.text is renamed to test003b.txt
        Wait for the client loop to go round again to perform sync.
        Both the client and server process are closed down.
        The server directory is inspected to see if test003b.txt is present.
        The server log is inspected to check for a local copy and rename.
        """
        logging.info('START - test_003_client_file_rename')
        logging.info('Starting the server process')
        with open('test_003_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Writing test003a.txt into the client directory')
        with open(os.path.join(self.CLIENT_FOLDER, 'test003a.txt'), 'w') as test_file:
            test_file.write('test_003_client_file_rename')

        logging.info('Starting the client process')
        with open('test_003_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test003a.txt is present
        for file in server_files:
            if file[1] == 'test003a.txt':
                found = True
                break
        if found:
            logging.info('test003a.txt has been found in the server directory')
        else:
            logging.error('test003a.txt has not been found in the server directory')
            self.assertTrue(False, 'test003a.txt has not been found in the server directory so test cannot proceed')

        logging.info('Renaming test003a.txt to test003b.txt in the client directory')
        os.rename(os.path.join(self.CLIENT_FOLDER, 'test003a.txt'), os.path.join(self.CLIENT_FOLDER, 'test003b.txt'))

        logging.info('Waiting for the client cycle to happen')
        time.sleep(self.CLIENT_CYCLE)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(25)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test001.txt is present
        for file in server_files:
            if file[1] == 'test003b.txt':
                found = True
                break
        if found:
            logging.info('test003b.txt has been found in the server directory')
        else:
            logging.error('test003b.txt has been not found in the server directory so server failed to rename')

        # Evaluate the result
        self.assertTrue(found, 'Failed to find the test003b.txt so sync failed')
        logging.info('Checking server log for local rename')
        log_line = 'Copying file: test003a.txt and renaming to test003b.txt'
        with open('test_003_server.log', 'r') as server_log:
            self.assertTrue(server_log.read().find(log_line) > 0, 'Failed to find the server log line for local rename')
        logging.info('END - test_003_client_file_rename')

    def test_004_client_file_modify(self):
        """
        Edit a file in the client directory and check that the server deletes its copy and requests a new one.

        First the server process is started.
        test004.txt is written into the client directory in preparation for running the client.
        md5 of test004.txt is stored for later comparison.
        The client process is then started.
        Time is given to allow the transaction to take place.
        The server directory is inspected to see if test004.txt is present.
        Clients test004.text is modifed.
        md5 of test004.txt is stored for later comparison.
        Wait for the client loop to go round again to perform sync.
        Both the client and server process are closed down.
        The server directory is inspected to see if test004.txt is present.
        md5 of test004.txt in the server directory checked against the original md5 to check for difference
        """
        logging.info('START - test_004_client_file_modify')
        logging.info('Starting the server process')
        with open('test_004_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Writing test004.txt into the client directory')
        with open(os.path.join(self.CLIENT_FOLDER, 'test004.txt'), 'w') as test_file:
            test_file.write('test_004_client_file_modify')

        # Get the original md5 of test file
        client_md5_original = self.get_file_md5(self.CLIENT_FOLDER, 'test004.txt')
        logging.info('Client test004.txt original md5: ' + str(client_md5_original))

        logging.info('Starting the client process')
        with open('test_004_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test003a.txt is present
        for file in server_files:
            if file[1] == 'test004.txt':
                found = True
                break
        if found:
            logging.info('test004.txt has been found in the server directory')
        else:
            logging.error('test004.txt has not been found in the server directory')
            self.fail('test004.txt has not been found in the server directory so test cannot proceed')

        # Get the servers test004.txt md5
        server_md5_original = self.get_file_md5(self.SERVER_FOLDER, 'test004.txt')
        logging.info('Server test004.txt original md5: ' + str(server_md5_original))

        logging.info('Editing test004.txt to change the md5')
        with open(os.path.join(self.CLIENT_FOLDER, 'test004.txt'), 'w') as test_file:
            test_file.write('test_004_client_file_modify edited file')

        # Get the new md5 of test file
        client_md5_new = self.get_file_md5(self.CLIENT_FOLDER, 'test004.txt')
        logging.info('Client test004.txt new md5: ' + str(client_md5_new))

        if client_md5_original == client_md5_new:
            self.fail('Failed to modify the md5 of the client file')

        logging.info('Waiting for the client cycle to happen')
        time.sleep(self.CLIENT_CYCLE)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test001.txt is present
        for file in server_files:
            if file[1] == 'test004.txt':
                found = True
                break
        if found:
            logging.info('test004.txt has been found in the server directory')
        else:
            logging.error('test004.txt has been not found in the server directory so server failed to rename')
            self.fail('Failed to find test004.txt so test cannot continue')

        # Get the servers test004.txt new md5
        server_md5_new = self.get_file_md5(self.SERVER_FOLDER, 'test004.txt')
        logging.info('Server test004.txt new md5: ' + str(server_md5_new))

        # Compare the md5 of client and server files
        result = (server_md5_new == client_md5_new)
        if result:
            logging.info('Server file successfully updated')
        else:
            logging.error('Server file was not updated')

        self.assertTrue(result, 'The md5 of the client and server test004.txt do not match')
        logging.info('END - test_004_client_file_modify')

    def test_005_client_file_add_with_same_md5(self):
        """
        Add a file in the client directory that is identical to an existing on by all but name and check that the
        server does a local copy and rename instead of requesting the file.

        First the server process is started.
        test005a.txt is written into the client directory in preparation for running the client.
        md5 of test005a.txt is stored for later comparison.
        The client process is then started.
        Time is given to allow the transaction to take place.
        The server directory is inspected to see if test005a.txt is present.
        test005a.text is copied to test005b.txt on client.
        md5 of test005b.txt is stored for later comparison.
        Wait for the client loop to go round again to perform sync.
        Both the client and server process are closed down.
        The server directory is inspected to see if test005b.txt is present.
        md5 of test005b.txt in the server directory checked against the test005a.txt md5 to check for match.
        Server log inspected for local copy and rename.
        """
        logging.info('START - test_005_client_file_add_with_same_md5')
        logging.info('Starting the server process')
        with open('test_005_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Writing test005a.txt into the client directory')
        with open(os.path.join(self.CLIENT_FOLDER, 'test005a.txt'), 'w') as test_file:
            test_file.write('test_005_client_file_add_with_same_md5')

        # Get the original md5 of test file
        client_md5_a = self.get_file_md5(self.CLIENT_FOLDER, 'test005a.txt')
        logging.info('Client test005a.txt original md5: ' + str(client_md5_a))

        logging.info('Starting the client process')
        with open('test_005_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test003a.txt is present
        for file in server_files:
            if file[1] == 'test005a.txt':
                found = True
                break
        if found:
            logging.info('test005a.txt has been found in the server directory')
        else:
            logging.error('test005a.txt has not been found in the server directory')
            self.fail('test005a.txt has not been found in the server directory so test cannot proceed')

        # Get the servers test005a.txt md5
        server_md5_a = self.get_file_md5(self.SERVER_FOLDER, 'test005a.txt')
        logging.info('Server test005a.txt original md5: ' + str(server_md5_a))

        logging.info('Copying test005a.txt to test005b.txt')
        shutil.copy(os.path.join(self.CLIENT_FOLDER, 'test005a.txt'), os.path.join(self.CLIENT_FOLDER, 'test005b.txt'))

        # Get the new md5 of test file
        client_md5_b = self.get_file_md5(self.CLIENT_FOLDER, 'test005b.txt')
        logging.info('Client test005b.txt new md5: ' + str(client_md5_b))

        if client_md5_a != client_md5_b:
            self.fail('Failed to copy test005a.txt to test005b.txt with matching md5')

        logging.info('Waiting for the client cycle to happen')
        time.sleep(self.CLIENT_CYCLE)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(30)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test001.txt is present
        for file in server_files:
            if file[1] == 'test005b.txt':
                found = True
                break
        if found:
            logging.info('test005b.txt has been found in the server directory')
        else:
            logging.error('test005b.txt has been not found in the server directory so server failed to rename')
            self.fail('Failed to find test005b.txt so test cannot continue')

        # Get the servers test005b.txt md5
        server_md5_b = self.get_file_md5(self.SERVER_FOLDER, 'test005b.txt')
        logging.info('Server test005b.txt new md5: ' + str(server_md5_b))

        # Compare the md5 of client and server files
        result = (server_md5_a == client_md5_b)
        if result:
            logging.info('Server file successfully updated')
        else:
            logging.error('Server file was not updated')

        self.assertTrue(result, 'The md5 of the client and server test005b.txt do not match')
        logging.info('Checking server log for local rename')
        log_line = 'Copying file: test005a.txt and renaming to test005b.txt'
        with open('test_005_server.log', 'r') as server_log:
            self.assertTrue(server_log.read().find(log_line) > 0, 'Failed to find the server log line for local rename')

        logging.info('END - test_005_client_file_add_with_same_md5')

    def test_006_server_file_add(self):
        """
        Add a file to the server and check that it is removed after the sync.

        test006.txt is written into the server directory in preparation for running the client.
        First the server process is started.
        The client process is then started.
        Time is given to allow the transaction to take place.
        The server directory is checked to ensure the file has been deleted.
        """
        logging.info('START - test_006_server_file_add')
        logging.info('Writing test006.txt into the server directory')
        with open(os.path.join(self.SERVER_FOLDER, 'test006.txt'), 'w') as test_file:
            test_file.write('test_006_server_file_add')

        time.sleep(10)
        logging.info('Starting the server process')
        with open('test_006_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Starting the client process')
        with open('test_006_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test001.txt is present
        for file in server_files:
            if file[1] == 'test006.txt':
                found = True
                break
        if found:
            logging.error('test006.txt has been found in the server directory so deletion failed')
        else:
            logging.info('test006.txt has been not found in the server directory')

        self.assertFalse(found, 'Failed to delete file from server upon sync')

        logging.info('END - test_006_server_file_add')

    def test_007_server_file_delete(self):
        """
        Delete a file from the server and check that the file is requested again.

        First the server process is started.
        test007.txt is written into the client directory in preparation for running the client.
        The client process is then started.
        Time is given to allow the transaction to take place.
        test007.txt is deleted from the server directory.
        Wait for the client loop to go round again to perform sync.
        Both the client and server process are closed down.
        The server directory is inspected to see if test007.txt is present.
        """
        logging.info('START - test_007_server_file_delete')
        logging.info('Starting the server process')
        with open('test_007_server.log', 'w') as server_log:
            server_process = subprocess.Popen(['python3', 'server-sync.py', self.SERVER_FOLDER], stdout=server_log)
        time.sleep(10)

        logging.info('Writing test007.txt into the client directory')
        with open(os.path.join(self.CLIENT_FOLDER, 'test007.txt'), 'w') as test_file:
            test_file.write('test_007_server_file_delete')
        test_file.close()

        logging.info('Starting the client process')
        with open('test_007_client.log', 'w') as client_log:
            client_process = subprocess.Popen(['python3', 'client-sync.py', self.CLIENT_FOLDER], stdout=client_log)
        logging.info('Waiting for the server and client to perform the sync and close the processes')
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test007.txt is present
        for file in server_files:
            if file[1] == 'test007.txt':
                found = True
                break
        if found:
            logging.info('test007.txt has been found in the server directory')
        else:
            logging.error('test007.txt has not been found in the server directory')
            self.fail('Failed to copy file to server')

        # Delete the file off the server
        logging.info('Deleting file off the server')
        os.remove(os.path.join(self.SERVER_FOLDER, 'test007.txt'))

        logging.info('Waiting for the client cycle to happen')
        time.sleep(self.CLIENT_CYCLE*2)

        # Close the client and server
        client_process.terminate()
        client_process.wait()
        server_process.terminate()
        server_process.wait()
        time.sleep(20)

        logging.info('Getting a directory listing from the server directory')
        server_files = self.read_storage(self.SERVER_FOLDER)
        found = False
        # Search the file list and see if the test007.txt is present
        for file in server_files:
            if file[1] == 'test007.txt':
                found = True
                break
        if found:
            logging.info('test007.txt has been found in the server directory')
        else:
            logging.error('test007.txt has not been found in the server directory')

        # Evaluate the result
        self.assertTrue(found, 'Failed to find the test007.txt so sync failed')
        logging.info('END - test_007_server_file_delete')


if __name__ == '__main__':
    unittest.main()
