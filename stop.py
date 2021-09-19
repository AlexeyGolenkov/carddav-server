import os

login = input('login: ')

cmd = 'docker ps -a > containers'
os.system(cmd)

file = open('containers', 'r')
lines = file.readlines()

for line in lines:
    if line.find(login.lower() + '-carddavserver') != -1:
        os.system('docker container stop ' + line.split(' ')[0])
        os.system('docker container rm ' + line.split(' ')[0])

import shutil
try:
    os.remove('containers')
except:
    pass

file.close()
