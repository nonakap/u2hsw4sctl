#!/usr/bin/env python
# 
# Copyright (C) 2012 NONAKA Kimihiro <nonakap@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#
# ELECOM U2H-SW4S USB port power control tool
#
# require: pyusb, libusb
# tested on python-2.7.2, pyusb-1.0.0a2, libusb-win32-bin-1.2.6.0
#

#
# Device Descriptor:
# bcdUSB:             0x0200
# bDeviceClass:         0x00
# bDeviceSubClass:      0x00
# bDeviceProtocol:      0x00
# bMaxPacketSize0:      0x40 (64)
# idVendor:           0x2101
# idProduct:          0x8501
# bcdDevice:          0x0605
# iManufacturer:        0x01
# iProduct:             0x02
# iSerialNumber:        0x00
# bNumConfigurations:   0x01
#
# ConnectionStatus: DeviceConnected
# Current Config Value: 0x01
# Device Bus Speed:     Full
# Device Address:       0x02
# Open Pipes:              1
#
# Endpoint Descriptor:
# bEndpointAddress:     0x82
# Transfer Type:   Interrupt
# wMaxPacketSize:     0x0008 (8)
# bInterval:            0x08
#

import usb.core
import usb.util
import struct

VENDOR=0x2101
PRODUCT=0x8501

PORT_MIN=1
PORT_MAX=4

PORT_FULLLIST = range(PORT_MIN, PORT_MAX + 1)

class U2HSW4SPortPower(object):

    def __init__(self, vendor = VENDOR, product = PRODUCT):
        # find our device
        self.dev = usb.core.find(idVendor = vendor, idProduct = product)

        # was it found?
        if self.dev is None:
            raise ValueError('Device not found')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.dev.set_configuration()

    #
    # Send control message
    #
    def _send(self, msg):
        return self.dev.ctrl_transfer(bmRequestType = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_INTERFACE, bRequest = 9, wValue = 0x203, data_or_wLength = msg, timeout = 100)

    #
    # Convert port# to address#
    #
    def _port_to_addr(self, port):
        addrs = ( 5, 2, 3, 4 )
        if port < 1:
            return -1
        port = port - 1
        if port >= len(addrs):
            return -1
        return addrs[port]

    #
    # Get port status
    #
    def getStatus(self):
        # get an endpoint instance
        cfg = self.dev.get_active_configuration()
        interface_number = cfg[(0,0)].bInterfaceNumber
        try:
            alternate_setting = usb.control.get_interface(self.dev, interface_number)
        except usb.core.USBError:
            alternate_setting = 0
        intf = usb.util.find_descriptor(cfg, bInterfaceNumber = interface_number, bAlternateSetting = alternate_setting)
        ep = usb.util.find_descriptor(intf, custom_match = lambda e: usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR)
        assert ep is not None

        msg = '\x03\x5d\x02\x00\x00\x00\x00\x00'
        assert len(msg) == 8
        ret = self._send(msg)
        assert ret == 8

        data = ep.read(size = 8, timeout = 100)
        assert len(data) == 8
        assert data[0] == 0x03
        assert data[1] == 0x5d
        assert data[3] == 0x00
        assert data[4] == 0x75
        assert data[5] == 0x00
        assert data[6] == 0x00
        assert data[7] == 0x00

        status = {}
        for port in PORT_FULLLIST:
            addr = self._port_to_addr(port)
            assert addr >= 0
            status[port] = (data[2] >> addr) & 1
        return status

    #
    # Set port power
    #
    def setPower(self, port, onoff):
        addr = self._port_to_addr(port)
        assert addr >= 0
        msg = struct.pack('BBBBBBBB', 0x03, 0x5d, 0x00, addr, onoff, 0x00, 0x00, 0x00)
        assert len(msg) == 8
        ret = self._send(msg)
        assert ret == 8

if __name__ == '__main__':
    import sys
    argc = len(sys.argv)
    argv = sys.argv

    def usage():
        print 'Usage: %s [<port> [onoff]]' % argv[0]
        print 'port : 1-4'
        print 'onoff: on, off'
        quit()

    if argc < 1 or argc >= 4:
        usage()

    inst = U2HSW4SPortPower()

    def getStatus(port, status):
        pstatus = ( 'Off', 'On' )
        return pstatus[status[port]]

    if argc == 1:
        status = inst.getStatus()
        for port in PORT_FULLLIST:
            print "Port%d: %s" % (port, getStatus(port, status))
        quit()

    port = int(argv[1])
    if port < PORT_MIN or port > PORT_MAX:
        usage()

    if argc == 2:
        status = inst.getStatus()
        print getStatus(port, status)
        quit()

    if argv[2].upper() == "ON":
        onoff = 1
    elif argv[2].upper() == "OFF":
        onoff = 0
    else:
        usage()

    oldstatus = inst.getStatus()
    inst.setPower(port, onoff)
    newstatus = inst.getStatus()
    print "Port%d: %s -> %s" % (port, getStatus(port, oldstatus), getStatus(port, newstatus))
