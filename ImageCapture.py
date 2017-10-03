#!/usr/bin/env python
# coding: interpy

import webbrowser as wb

import sys,os,re,smtplib,fcntl,webbrowser
import subprocess,time,cv2,socket,struct,urllib2

from gdm import gdm
from name import user
from fileops import ops
from tailf import tailf
from optparse import OptionParser

from subprocess import Popen, call
from email.MIMEImage import MIMEImage
from email.MIMEMultipart import MIMEMultipart

parser = OptionParser()
parser.add_option("-e", "--email", dest='email')
parser.add_option("-p", "--password", dest='password')
parser.add_option("-v", "--video", dest='video', default=0, help="Specify camera location.")
parser.add_option("-P", "--port", dest='port', default=587, help="E-mail port defaults to 587 if not specified.")
parser.add_option("-a", "--attempts", dest='attempts', default=3, help="Number of failed attempts defaults to 3.")
parser.add_option("-L", "--location", dest='location', action="store_true", default=False, help="Enable location capturing.") 
parser.add_option("-l", "--log-file", dest='logfile', default='/var/log/auth.log', help="Tail log defaults to /var/log/auth.log.")
parser.add_option("-c", "--enable-cam", dest='enablecam', action="store_true", default=False, help="Enable cam capture of intruder.")
parser.add_option("-A", "--auto-login", dest='autologin', action="store_true", default=False, help="Auto login user after no of failed attempts.")
parser.add_option("-C", "--clear-autologin", dest='clear', action="store_true", default=False, help="Remove autologin. Must be root to use this feature.")
parser.add_option("-s", "--allow-sucessful", dest='allowsucessful', action="store_true", default=False, help="Run ImageCapture even if login is sucessful.")
(options, args) = parser.parse_args()

print "options: #{options}\n"

if not ops.fileExists(options.logfile):
    logfile = '/var/log/auth.log'
else:
    logfile = options.logfile

if options.video is not None:
    video = options.video
else:
    video = 0

if options.email is not None:
    send_email = True
    sender,to = options.email,options.email

if options.password is not None:
    send_email = True
    password = options.password

if options.password is None or options.email is None:
    send_email = False

user           = user.name()
port           = options.port
clear          = options.clear
attempts       = options.attempts
location       = options.location
enablecam      = options.enablecam
allowsucessful = options.allowsucessful

def connected():
    try:
        urllib2.urlopen('http://www.google.com', timeout=1)
        return True
    except urllib2.URLError as err:
        return False

def getHwAddr(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    return ':'.join(['%02x' % ord(char) for char in info[18:24]])

#print getHwAddr('wlo1')

def getLocation():
    if not location:
        return
    while ops.readFile("true", user):
        if connected():
            time.sleep(3)
            call(["/opt/google/chrome/chrome", 
                "--user-data-dir=/home/#{user}/.imagecapture", "--no-sandbox", 
                "https://justdrive-app.com/imagecapture/index.html?Email=#{to}"])
            ops.writeFile('false', user)
            if send_email:
                sendMail(sender,to,password,port,'Failed GDM login!',
                    "Someone tried to login into your computer and failed #{attempts} times.")
        else:
            break

def takePicture():
    camera = cv2.VideoCapture(video)
    if not camera.isOpened():
        print "No cam available at #{video}"
        return
    elif not enablecam:
        print "Taking pictures from webcam was not enabled."
        return
    elif not camera.isOpened() and video == 0:
        print "ImageCapture does not detect a camera."
        return
    print "Taking picture."
    time.sleep(0.1) # Needed or image will be dark.
    image = camera.read()[1]
    cv2.imwrite("/home/#{user}/.imagecapture/intruder.png", image)
    del(camera)

def sendMail(sender,to,password,port,subject,body):
    try:
        message = MIMEMultipart()
        message['Body'] = body
        message['Subject'] = subject
        message.attach(MIMEImage(file("/home/#{user}/.imagecapture/intruder.png").read()))
        mail = smtplib.SMTP('smtp.gmail.com',port)
        mail.starttls()
        mail.login(sender,password)
        mail.sendmail(sender, to, message.as_string())
        print "\nSent email successfully.\n"
    except smtplib.SMTPAuthenticationError:
        print "\nCould not athenticate with password and username!\n"
    except:
        print("Unexpected error in sendMail():", sys.exc_info()[0])
        raise

def initiate(count):
    if count == attempts or options.allowsucessful:
        return True
    else:
        return False

def tailFile(logfile):

    count = 0

    gdm.autoLoginRemove(options.autologin, user)

    for line in tailf(logfile):

        s = re.search("(^.*\d+:\d+:\d+).*password.*pam: unlocked login keyring", line, re.I | re.M)
        f = re.search("(^.*\d+:\d+:\d+).*pam_unix.*:auth\): authentication failure", line, re.I | re.M)

        if f and not allowsucessful:
            count += 1
            sys.stdout.write("Failed login via GDM at #{f.group(1)}:\n#{f.group()}\n\n")
            if initiate(count):
                gdm.autoLogin(options.autologin, user)
                takePicture()
                ops.writeFile('true', user)
                getLocation()
            time.sleep(1)
        if s and allowsucessful:
            sys.stdout.write("Sucessful login via GDM at #{s.group(1)}:\n#{s.group()}\n\n")
            gdm.autoLogin(options.autologin, user)
            takePicture()
            ops.writeFile('true', user)
            getLocation()
            time.sleep(1)

gdm.clearAutoLogin(options.clear, user)
getLocation()

while True:
    tailFile(logfile)
