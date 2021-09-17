import os
import hashlib

def gen(login):
    return login + "-cdserver"

login = input('Login: ')
password = input('Password: ')

print('What do you want to do? Run server(1) or export contacts(2)')
s = input()

if s == '2':
    directory = './CDserver/collections/collection-root/' + login + '/' + '44de64b3-ff87-69cb-b042-7fe19dfa7d31'
    try:
        files = os.listdir(directory)
        vcf = list(filter(lambda x: x.endswith('.vcf'), files))
        res = ''
        for i in vcf:
            f = open(directory + '/' + i, 'r')
            res += f.read()
            f.close()
        f = open('result.vcf', 'w')
        f.write(res)
        f.close()
        print(res)
    except:
        print('The user does not exist. The server with this user was never started. Start the server and then try to pull contacts')
else:
    result = open('log_info', 'w')
    result.write(login + '\n' + password)
    result.close()

    conf = open('config.yml', "w")
    conf.write('authtoken: 1xBoAK07qHZoQ0aD9Fg6Q5HPHJ6_4wAbUj9k6YRyhw88aKt8D\n')
    conf.write('tunnels:\n')
    conf.write('    cds:\n')
    conf.write('        proto: http\n')
    conf.write('        addr: 5232\n')
    conf.write('        subdomain: ' + gen(login))
    conf.close()

    import shutil
    try:
        shutil.copytree('CDserver/collections/collection-root/' + login, 'collection-root/' + login)
        shutil.rmtree('CDserver/collections/collection-root/' + login)
    except:
        print('new user')

    cmd = 'docker build -t carddavserver .'
    os.system(cmd)
    cmd = 'docker run -v `pwd`:/CDserver/collections -p 5232:5232 carddavserver'
    os.system(cmd)

    try:
        shutil.copytree('collection-root/' + login, 'CDserver/collections/collection-root/' + login)
        shutil.rmtree('collection-root/')
    except:
        print('interesting')

    os.remove('log_info')
    os.remove('config.yml')