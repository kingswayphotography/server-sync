**server-sync project**

A client server project written in Python 3 to keep two directories in sync via TCP

**client-sync.py**

A commandline client that takes one argument which is the local directory it should monitor and relay changes to the server.

The client is hardcoded to use **localhost** as the address for the server and **7101** as the port for the server.
There is an additional port used for file data transfer which is **7100**.

Upon running client connects to the server and sends a list of files (with md5's) which are contained within the directory passed as an argument.

It then waits for a response from the server in the form of either a **filerequest** or **sync:done** message.

If a **sync:done** is received then no files are required from the client by the server. 
The connection to the server is then closed and a 60s wait before contacting the server again.

If a **filerequest** message is received then one message parameter is passed with it which contains the file to send in the following format: **[[file location, file name, file md5]]** .
Upon receipt of this message the client opens up a second connection to the server on port **7100** and sends the file data, closing the connection upon completion of each file.

It then continues to process any addition **filerequest** messages from the server until a **sync:done** is received.

**server-sync.py**

A commandline server that takes one argument which is the local directory it should keep in sync with the client.

The server is hardcoded to use **localhost** as the address for the server and **7101** as the port for the server.
There is an additional port used for file data transfer which is **7100**.

Upon running the server reads in a list of files from the directory specified as an argument, opens up a socket to allow clients to connect on the previously mentioned port.
It then enters a loop awaiting connections.

When a client is connected the server then waits for a **filelist** message from the client. With that message the client provides a list of files in this format **[[file 1 location, file 1 name, file 1 md5],[file 2 location, file 2 name, file 2 md5]...]** .

With that list of files from the client it then compares this data with the list of files the server has.
In the comparison it then does the following:
* Checks for any files the server is missing by file name, if a file is missing then it checks for any files locally that have the same md5, if it finds a match then that file is copied locally and renamed to avoid requesting/processing files it already has. If no match is found the file is added to the request list.
* Checks for any files the client no longer has which can be deleted.
* Checks for any files that have changed by comparing the md5 of the file, adding them to a request list upon discovery.

Once the list is compared the server copies and renames any files first (just in case they are on the list of files to delete). 
It then deletes any files that are no longer required.

The next step is it sending a **filerequest** message to the client on a per file basis, opening a second port to receive the file data and saving it locally.

Finally once all the files have been requested and received the server sends a **sync:done** message to the client informing it that it has finished and the client can disconnect.

**Running**

* Start the server running first from commandline:
`python3 server-sync.py /dir/to/keep/in/sync`
* Then start the client from the commandline:
`python3 client-sync.py /dir/to/keep/in/sync`

No trailing slash is required on the file path argument for either python script. 

**test-sync**

Before running the tests the variables in in the ServerSyncTest class need setting for the CLIENT_FOLDER and SERVER_FOLDER.
Make sure they are empty folders to ensure a clean test environment.

To run the tests from the commandline:
`python3 test-sync.py`

The tests that re performed as as follows:
* 001 - Add a file to the client folder
* 002 - Delete a file from the client folder
* 003 - Rename a file in the client folder
* 004 - Modify a file in the client folder
* 005 - Add a file to client folder with matching md5 to an exising file
* 006 - Add a file to the server directory
* 007 - Delete a file from the server directory

The main logs for the tests are saved to **test_sync.log**. 
For each test a log is taken from the server process and saved to **test_XXX_server.log** where XXX is the test number.
Likewise for each test run the client process logs are saved to **test_XXX_client.log**.