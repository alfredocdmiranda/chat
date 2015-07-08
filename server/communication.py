# -*- coding: utf-8 -*-

import cPickle
import socket
import struct

marshall = cPickle.dumps
unmarshall = cPickle.loads

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
