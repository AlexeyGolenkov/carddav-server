## Requirements

```bash
python3
```

```bash
Docker
```

## Installation

Clone the repository

```bash
git clone https://github.com/AlexeyGolenkov/carddav-server
```

## Running the server

Go to the folder

```bash
cd carddav-server
```

Run 'run.py'
```bash
python3 run.py
```

If the program returns 'Permission denied', put 'sudo' before the command.

Enter the login and password (if you use the program first time, it will create a new user)

## Connecting to the server
When you connect to the server, each client will require server name. You should type
```bash
https://cdserver.ngrok.io
```
Then type your login and password you entered in the previous step.

## Close the server

In another terminal window run the following command and wait for a while until the program is completed
```bash
python3 stop.py
```
