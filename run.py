import os

login = input('Login: ')
password = input('Password: ')

print('What do you want to do? Run server(1) or export contacts(2)')
s = input()

if s == '2':
    directory = './CDserver/collections/collection-root/' + login + '/' + '44de64b3-ff87-69cb-b042-7fe19dfa7d31'
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
else:
    result = open('log_info', 'w')
    result.write(login + '\n' + password)
    result.close()

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
        shutil.rmtree('collection-root/' + login)
    except:
        print('interesting')

    os.remove('log_info')
