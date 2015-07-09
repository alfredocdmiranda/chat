# -*- coding: utf-8 -*-

try:
    import cPickle as pickle
except ImportError:
    import pickle
import socket
import struct

marshall = pickle.dumps
unmarshall = pickle.loads

BUFFSIZE = 512

def send(channel, msg):
    data = msg.encode('UTF-8')
    data += " "*(512-len(data))
    channel.send(data)
    
    return True

def receive(channel):
    data = channel.recv(BUFFSIZE)
    data = data.decode('UTF-8')
    index = data.find('\n\r')
    data = data[0:index]

    return data
