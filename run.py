import os
import hashlib

def gen(login):
    return login + '-cdserver'

login = input('Login: ')
password = input('Password: ')

print('What do you want to do? 1 - Run server. 2 - export contacts. 3 - import contacts.')
s = input()

if s == '3':
    path = input('path to contacts - ')
    try:
        file = open(path)
        lines = file.readlines()
        file.close()
        i = 0
        cur = ""
        for line in lines:
            cur += line
            if line == 'END:VCARD\n':
                cur_dir = 'CDserver/collections/collection-root/' + login + '/contacts'
                try:
                    os.makedirs(cur_dir)
                except:
                    pass
                out = open(cur_dir + '/' + str(i) + '.vcf', "w")
                out.write(cur)
                out.close()
                cur = ""
                i += 1
    except:
        print('couldn\'t open the contacts file')
elif s == '2':
    directory = './CDserver/collections/collection-root/' + login + '/' + 'contacts'
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

    dname = login + '-carddavserver'
    cmd = 'docker build -t ' + dname + ' .'
    os.system(cmd)
    cmd = 'docker run -v `pwd`:/CDserver/collections -p 5232:5232 ' + dname
    os.system(cmd)

    try:
        shutil.copytree('collection-root/' + login, 'CDserver/collections/collection-root/' + login)
        shutil.rmtree('collection-root/')
    except:
        print('interesting')

    try:
        os.remove('log_info')
    except:
        pass

    try:
        os.remove('config.yml')
    except:
        pass