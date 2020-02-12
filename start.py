from os import path, system
from time import sleep

print('Welcome to MixPlayer`s whatchdog!\n')
currentPath = path.dirname(path.realpath(__file__))
while True:
	system('python ' + currentPath + '/MIXplayer.py')
	print('\nRestart in 10 seconds...')
	sleep(10)
