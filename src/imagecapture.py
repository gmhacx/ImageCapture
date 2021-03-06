#!/usr/bin/env python

# PEP8 compliant import structure.
import os
import re
import sys
import cv2
import time
import errno
import fcntl
import select
import socket
import struct
import logging
import sqlite3
import smtplib
import webbrowser
import subprocess
import multiprocessing
import logging.handlers
 
from urllib2 import urlopen
from optparse import OptionParser
from subprocess import Popen,call
from email.MIMEImage import MIMEImage
from distutils.spawn import find_executable
from email.MIMEMultipart import MIMEMultipart

# importing urllib2 works on my Linux Mint
# box but not my Gentoo box and here is the fix!
try:
    import urllib2
except ImportError:
    import urllib

class Logging(object):

    def log(self,level,message):
        comm = re.search("(WARN|INFO|ERROR)", str(level), re.M)
        try:
            handler = logging.handlers.WatchedFileHandler(
                os.environ.get("LOGFILE","/var/log/sshmonitor.log")
            )
            formatter = logging.Formatter(logging.BASIC_FORMAT)
            handler.setFormatter(formatter)
            root = logging.getLogger()
            root.setLevel(os.environ.get("LOGLEVEL", str(level)))
            root.addHandler(handler)
            # Log all calls to this class in the logfile no matter what.
            if comm is None:
                print(level + " is not a level. Use: WARN, ERROR, or INFO!")
                return
            elif comm.group() == 'ERROR':
                logging.error(str(time.asctime(time.localtime(time.time()))
                + " - ImageCapture - "
                + str(message)))
            elif comm.group() == 'INFO':
                logging.info(str(time.asctime(time.localtime(time.time()))
                + " - ImageCapture - "
                + str(message)))
            elif comm.group() == 'WARN':
                logging.warn(str(time.asctime(time.localtime(time.time()))
                + " - ImageCapture - "
                + str(message)))
            # Print to stdout only if the verbose option is passed or log level = ERROR.
            if options.verbose or str(level) == 'ERROR':
                print("(" + str(level) + ") "
                + str(time.asctime(time.localtime(time.time()))
                + " - ImageCapture - "
                + str(message)))
        except IOError as eIOError:
            if re.search('\[Errno 13\] Permission denied:', str(eIOError), re.M | re.I):
                print("(ERROR) ImageCapture - Must be sudo to run ImageCapture!")
                sys.exit(0)
            print("(ERROR) ImageCapture - IOError in Logging class => "
                + str(eIOError))
            logging.error(str(time.asctime(time.localtime(time.time()))
                + " - ImageCapture - IOError => "
                + str(eIOError)))
        except Exception as exception:
            print("(ERROR) ImageCapture - Exception in Logging class => " + str(exception))
            logging.error(str(time.asctime(time.localtime(time.time()))
                + " - ImageCapture - Exception => "
                + str(exception)))
            pass
        return

# The config filename is passed to this class in the ImageCapture classes __init__ method.
# The option is the default value set in optparser and is blank by default. See the 
# optparser declaration at the bottom in the if __name__ == '__main__' check.
class ConfigFile(object):

    def __init__(self, file_name):
        self.args_list = []
        self.file_name = file_name
        if file_name:
            try:
                self.config_file = open(file_name,'r').read().splitlines()
                self.config_file_syntax_sanity_check()
            except IOError:
                logger.log("ERROR","Config file does not exist.")
                sys.exit(0)

    def __getattr__(self, key):
        pass

    def __setattr__(self, key, val):
        pass

    # If a config file is 'NOT' passed via command line then this method will set the global
    # base variables for the config_dict data structure using the optparsers default values.
    # ---
    # If a config file 'IS' passed via command line then this method will read in the options
    # values and set the base options for the global config_dict data structure. If the config
    # files options have empty values then those options are loaded into an array nested inside
    # of the config_dict data structure. Which will later be used as a reference against the 
    # config_data structure so it knows to use optparsers default values for these options.
    def config_options(self):
        # If config file is 'NOT' supplied use optparsers default values.
        if not self.file_name:
            for default_opt in config_dict[0].keys():
                config_dict[0][default_opt][0] = config_dict[0][default_opt][1]
                logger.log("INFO", "Setting option("
                    + default_opt + "): "
                    + str(config_dict[0][default_opt][0]))
            return
        # If the config file exists and the syntax is correct we will have to convert the
        # 'bool' values in the file which are being loaded in as strings to actual bool values.
        # The same applies for integers otehrwise load the values in as is.
        for line in self.config_file:
            comm = re.search(r'(^.*)=(.*)', str(line), re.M | re.I)
            if comm is not None:
                if not comm.group(2):
                    config_dict[1].append(comm.group(1))
                elif re.search('true', comm.group(2), re.I) is not None:
                    config_dict[0][comm.group(1)][0] = True
                elif re.search('false', comm.group(2), re.I) is not None:
                    config_dict[0][comm.group(1)][0] = False
                elif re.search('([0-9]{1,6})', comm.group(2)) is not None:
                    config_dict[0][comm.group(1)][0] = int(comm.group(2))
                else:
                    config_dict[0][comm.group(1)][0] = comm.group(2)
        return config_dict

    # If command line options 'ARE' passed via optparser/command line then this method
    # will override the default values set with optparser as well as override the options
    # in the config file that was passed.
    def override_values(self):
        for default_opt in config_dict[0].keys():
            comm = re.search('-(\w{0,9}|)'
                + config_dict[0][default_opt][2], str(sys.argv[1:]), re.M)
            if comm is not None:
                logger.log("INFO", "Overriding "
                    + str(default_opt)
                    + " default value with command line switch value("
                    + str(config_dict[0][default_opt][1]) + ")")
                config_dict[0][default_opt][0] = config_dict[0][default_opt][1]

    # If a config file is supplied then this method will use the default options
    # in optparser if the option in the config file has no value. So if the password 
    # option in the config file looks like this -> password= then it will be populated 
    # by this method.
    def populate_empty_options(self):
        if config_dict[1] and self.config_file_supplied():
            for opt in config_dict[1]:
                config_dict[0][opt][0] = config_dict[0][opt][1]

    def config_file_supplied(self):
        if re.search(r'(\-C|\-\-config\-file)',str(sys.argv[1:]), re.M) is None:
            return False
        return True

    def config_file_syntax_sanity_check(self):
        for line in self.config_file:
            comm = re.search(r'(^.*)=(.*)', str(line), re.M | re.I)
            if comm is not None:
                try:
                    config_dict[0][comm.group(1)]
                except KeyError:
                    logger.log("ERROR", "Config file option("
                        + comm.group(1)
                        + ") is not a recognized option!")
                    sys.exit(0)

class Tail(object):

    def __init__(self):
        self.buffer       = str()
        self.tail_command = ['/usr/bin/tail', '-F', '-n0']

    def process(self,filename):

        process = subprocess.Popen(
            self.tail_command + [filename], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    
        # set non-blocking mode for file
        function_control = fcntl.fcntl(process.stdout, fcntl.F_GETFL)
        fcntl.fcntl(process.stdout, fcntl.F_SETFL, function_control | os.O_NONBLOCK)
    
        function_control = fcntl.fcntl(process.stderr, fcntl.F_GETFL)
        fcntl.fcntl(process.stderr, fcntl.F_SETFL, function_control | os.O_NONBLOCK)
        
        return process
    
    def f(self, filename):

        process = self.process(filename)
        
        while True:
            reads, writes, errors = select.select(
                [process.stdout, process.stderr], [], [process.stdout, process.stderr], 0.1
            )
            if process.stdout in reads:
                self.buffer += process.stdout.read()
                lines = self.buffer.split('\n')
                
                if '' in lines[-1]:
                    #whole line received
                    self.buffer = str()
                else:
                    self.buffer = lines[-1]
                lines = lines[:-1]
    
                if lines:
                    for line in lines:
                        yield line
                    
            if process.stderr in reads:
                stderr_input = process.stderr.read()
    
            if process.stderr in errors or process.stdout in errors:
                print("Error received. Errors: ", errors)
                process = self.process(filename)                    

class ImageCapture(object):

    def __init__(self,config_dict={},file_name=''):
        # The order of these calls are important!
        configFile = ConfigFile(options.configfile)
        configFile.config_options()
        configFile.populate_empty_options()
        configFile.override_values()

        self.count  = 0
        self.date   = {}
        self.failed = None

        self.tail       = Tail()
        self.ip_addr    = urlopen('http://ip.42.pl/raw').read()
        self.send_email = False

        self.logfile_sanity_check(config_dict[0]['logfile'][0])
        database.add_ip_to_db(self.ip_addr)

        self.credential_sanity_check()
        self.broswer_path_sanity_check()
        self.location_sanity_check()
        self.display_options()

    # Display the final base options that the app has set and is using.
    def display_options(self):
        verbose = {}
        if config_dict[0]['verbose'][0]:
            for option in config_dict[0].keys():
                verbose[option] = config_dict[0][option][0]
            logger.log("INFO", "Options: " + str(verbose))

    def broswer_path_sanity_check(self):
        if (re.match("(\/)",config_dict[0]['browser'][0]) is None and
            config_dict[0]['location'][0]):
                logger.log("ERROR", "Please provide full path to browser!")
                sys.exit(0)

    def location_sanity_check(self):
        if config_dict[0]['location'][0]:
            if not self.send_email:
                logger.log("ERROR", "The location options requires an E-mail and password!")
                parser.print_help()
                sys.exit(0)
            elif not config_dict[0]['autologin'][0]:
                logger.log("ERROR","The location feature requires the autologin option(-A).")
                sys.exit(0)
            elif not len(os.listdir(fileOpts.root_directory())) > 2 or config_dict[0]['persistentlocation'][0]:
                self.get_location('init')

    # PEP8 states lines should not be over 80 characters long so I
    # wrote mulitline if/else statements enclosed in parenthesis.
    # ---
    # This method checks to see if you are passing both the E-mail
    # and password options together or not at all. If you do 'NOT' 
    # supply them both then the E-mail features will not work. It
    # sets the send_email variable to a bool value.
    def credential_sanity_check(self):
        if (not str(config_dict[0]['password'][0]) == 'password' and
            not str(config_dict[0]['email'][0]) == 'example@gmail.com'):
                self.send_email = True
        elif (str(config_dict[0]['password'][0]) == 'password' and
            str(config_dict[0]['email'][0]) == 'example@gmail.com'):
                self.send_email = False
        elif (str(config_dict[0]['password'][0]) == 'password' and
            not str(config_dict[0]['email'][0]) == 'example@gmail.com' or
            str(config_dict[0]['email'][0]) == 'example@gmail.com' and
            not str(config_dict[0]['password'][0]) == 'password'):
                logger.log("ERROR",
                    "Both the E-mail and password options must be supplied or none at all!")
                parser.print_help()
                sys.exit(0)

    def logfile_sanity_check(self,logfile):
        if config_dict[0]['clearautologin'][0]:
            return
        elif logfile is None:
            logger.log("ERROR", "Please specify a log file to tail!")
            parser.print_help()
            sys.exit(1)
        elif os.path.exists(logfile):
            config_dict[0]['logfile'][0] = logfile
            logger.log("INFO", "logfile(1): " + str(config_dict[0]['logfile'][0]))
        elif not os.path.exists(logfile):
            for log_file in ['messages']:
                if os.path.exists('/var/log/' + str(log_file)):
                    config_dict[0]['logfile'][0] = '/var/log/' + str(log_file)
                    logger.log("INFO", "logfile(2): " + str(config_dict[0]['logfile'][0]))
                    break
                else:
                    logger.log("ERROR","Log file " + logfile
                        + " does not exist. Please specify which log to use.")
                    sys.exit(0)

    def is_loction_supported(self,process):
        return find_executable(process) is not None
    
    def get_location(self,init=None):
        if not config_dict[0]['location'][0]:
            logger.log("INFO", "Location option is not enabled.")
            return
        elif config_dict[0]['location'][0] and not self.send_email:
            logger.log("ERROR",
                "Cannot E-mail your location without your E-mail and password. "
                + "Please use the --help option and search for -e and -p.")
            sys.exit(0)

        while database.read_from_db('location_bool') == 'true' or init == 'init':
            if Net.connected():
                time.sleep(3)
                database.add_location_to_db('false')
                if self.send_email:
                    try:
                        logger.log("INFO","Sending E-mail now.")
                        self.send_mail(
                            config_dict[0]['email'][0],
                            config_dict[0]['email'][0],
                            config_dict[0]['password'][0],
                            config_dict[0]['port'][0],
                            "Failed login from IP " + str(self.ip_addr) + "!",
                            "Someone tried to login into your computer and failed "
                            + str(config_dict[0]['attempts'][0]) + "times.")
                    except:
                        pass
                try:
                    logger.log("INFO","Grabbing location now.")
                    process = multiprocessing.Process(
                        target=GetLocation(
                            config_dict[0]['website'][0],
                            config_dict[0]['email'][0],
                            config_dict[0]['browser'][0]
                        ).launch_browser
                    )
                    process.daemon = True
                    process.start() 
                    if init == 'init':
                        break
                except Exception as exception:
                    logger.log("WARNING","Could not open your browser, error => "
                        + str(exception)
                        + ".")
                    pass
            else:
                break

    def executable_exists(self,executable_name):
        return find_executable(executable_name)
    
    def take_picture(self):
        if not config_dict[0]['enablecam'][0]:
            logger.log("WARNING","Taking pictures from webcam was not enabled.")
            return
        camera = cv2.VideoCapture(config_dict[0]['video'][0])
        if not camera.isOpened():
            logger.log("ERROR","No cam available at "
                + str(config_dict[0]['video'][0])
                + ".")
            config_dict[0]['enablecam'][0] = False
            return
        elif not camera.isOpened() and config_dict[0]['video'][0] == 0:
            logger.log("WARNING","Camera not detected.")
            config_dict[0]['enablecam'][0] = False
            return
        #elif self.executable_exists('/usr/local/bin/opencv') is None:
            #logger.log("WARNING", "OpenCV is not installed.")
            #config_dict[0]['enablecam'][0] = False
            #return
        try:
            logger.log("INFO","Taking picture.")
            time.sleep(0.1) # Needed or image will be dark.
            image = camera.read()[1]
            cv2.imwrite(fileOpts.picture_path(), image)
            del(camera)
        except Exception as exception:
            logger.log("ERROR", "Error taking picture, exception => "
                + str(exception))
    
    def send_mail(self,sender,to,password,port,subject,body):
        try:
            message = MIMEMultipart()
            message['Body'] = body
            message['Subject'] = subject
            if config_dict[0]['enablecam'][0]:
                message.attach(MIMEImage(file(fileOpts.picture_path()).read()))
            mail = smtplib.SMTP('smtp.gmail.com', port)
            mail.starttls()
            mail.login(sender,password)
            mail.send_mail(sender, to, message.as_string())
            logger.log("INFO","Sent email successfully!")
        except smtplib.SMTPAuthenticationError:
            logger.log("ERROR", "Could not athenticate with password and username!")
        except Exception as exception:
            logger.log("ERROR","Unexpected error in send_mail() => "+ str(exception))
    
    def failed_login(self,count):
        if (count == int(config_dict[0]['attempts'][0]) or
            config_dict[0]['allowsucessful'][0]):
                logger.log("INFO", "count: " + str(count))
                logger.log("INFO", "failed_login True")
                return True
        else:
            #logger.log("INFO", "failed_login False")
            return False

    def slimlock(self):
        _v = None

    def i3lock(self):
        _v = None
    
    def tail_file(self,logfile):
    
        gdm.auto_login_remove(config_dict[0]['autologin'][0], User.name())
    
        print("(INFO) ImageCapture - ImageCapture is ready!")
        print("(INFO) ImageCapture - Tailing logfile " + str(logfile))

        for line in self.tail.f(logfile):
    
            # Failed
            #'(^.*\d+:\d+:\d+).*'
            #May 18 12:04:21 anthony unix_chkpwd[13522]: password check failed for user (anthony) i3
            #May 18 12:20:46 anthony sshd[14392]: pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=127.0.0.1  user=anthony ssh
            #May 18 12:27:50 anthony slimlock[14639]: pam_succeed_if(slimlock:auth): requirement "user ingroup nopasswdlogin" not met by user "anthony" slim

            # Successful
            # May 19 16:00:01 anthony slimlock[4617]: pam_succeed_if(slimlock:auth): requirement "user ingroup nopasswdlogin" not met by user "anthony" slim

            success_regex = '(^.*\d+:\d+:\d+).*password.*pam: unlocked login keyring'

            success = re.search(success_regex, line, re.I | re.M)

            slimlock_regex1 = '(^\w+ \d+ \d+:\d+:\d+) .* slimlock\[\d+\]: '
            slimlock_regex2 = 'pam_succeed_if\(slimlock:auth\): requirement \".*\" not met by user'

            slimlock_regex  = re.search(slimlock_regex1+slimlock_regex2, str(line), re.I)

            if slimlock_regex:
                self.failed = slimlock_regex
            elif not slimlock_regex and not gdm.user_present(User.name()):
                logger.log("WARN", "This login manager is not supported! Only Slim is supported.")

            if self.failed and not config_dict[0]['allowsucessful'][0]:
                # Prevents the loop from producing duplicate positives
                if not self.date.has_key(self.failed.group(1)):
                    self.count += 1
                    self.date[str(self.failed.group(1))] = self.count
                    logger.log("INFO", "Failed login at "
                        + self.failed.group(1) + ":\n"
                        + self.failed.group() + "\n\n")
                if self.failed_login(self.count):
                    logger.log("INFO", "user: " + User.name())
                    gdm.auto_login(config_dict[0]['autologin'][0], User.name())
                    self.take_picture()
                    database.add_location_to_db('true')
                    self.get_location()
                    self.count += 1
                    if not config_dict[0]['enablecam'][0] and self.send_email:
                        try:
                            logger.log("INFO","Sending E-mail now.")
                            self.send_mail(
                                config_dict[0]['sender'][0],
                                config_dict[0]['email'][0],
                                config_dict[0]['password'][0],
                                config_dict[0]['port'][0],
                                "Failed login from IP " + self.ip_addr + "!",
                                "Someone tried to login into your computer and failed "
                                + config_dict[0]['attempts'][0] + " times.")
                        except:
                            pass
                time.sleep(1)
            if success and config_dict[0]['allowsucessful'][0]:
                logger.log("INFO", "Sucessful login at "
                    + success.group(1) + ":\n" 
                    + success.group() + "\n\n")
                gdm.auto_login(config_dict[0]['autologin'][0], User.name())
                self.take_picture()
                database.add_location_to_db('true')
                self.get_location()
                if not config_dict[0]['enablecam'][0] and self.send_email:
                    try:
                        logger.log("INFO","Sending E-mail now.")
                        self.send_mail(
                            config_dict[0]['sender'][0],
                            config_dict[0]['email'][0],
                            config_dict[0]['password'][0],
                            config_dict[0]['port'][0],
                            "Failed GDM login from IP " + self.ip_addr + "!",
                            "Someone tried to login into your computer and failed "
                            + config_dict[0]['attempts'][0] + " times.")
                    except:
                        pass
                time.sleep(1)
            else:
                pass
            time.sleep(1)

        db.add_ip_to_db(self.ip_addr)

    def main(self):

        _version_ = re.search('2.7',str(Version.python()), re.M | re.I)
        if _version_ is None:
            logger.log("ERROR", "Only python version 2.7 is supported.")
            sys.exit(0)
        logger.log("INFO", "Python version set to 2.7.")

        gdm.clear_auto_login(config_dict[0]['clearautologin'][0], User.name())
        self.get_location()

        try:
            self.tail_file(config_dict[0]['logfile'][0])
            #process = multiprocessing.Process(
                #target=self.tail_file, args=(config_dict[0]['logfile'][0],)
            #)
            #process.start()
        except IOError as ioError:
            logger.log("ERROR", "IOError: " + str(ioError))
        except KeyboardInterrupt:
            logger.log("INFO", " [Control C caught] - Exiting ImageCapturePy now!")
            process.terminate()
        except Exception as exception:
            logger.log("ERROR", "Exception in main(), exception => "+str(exception))

#        while True:
#            try:
#                self.tail_file(config_dict[0]['logfile'][0])
#            except IOError as ioError:
#                logger.log("ERROR", "IOError: " + str(ioError))
#            except KeyboardInterrupt:
#                logger.log("INFO", " [Control C caught] - Exiting ImageCapturePy now!")
#                break
#            except Exception as exception:
#                logger.log("ERROR", "Exception in main(), exception => "+str(exception))

# This class is used to grab the location of the laptop. The loacation data
# is in the form of longitude/latitude coordinates and is E-mailed to you.
# This is done through a website I wrote in PHP/HTML, Javascript, and JQuery 
# using a post request that is sent to heroku.
class GetLocation(object):

    def __init__(self,website,email,browser):
        self._email_,config_dict[0]['email'][0]   = (email,email)
        self._website_,config_dict[0]['website'][0] = (website,website)
        self._browser_,config_dict[0]['browser'][0] = (browser,browser)

    def browser_exists(self,browser):
        return find_executable(browser)

    def launch_browser(self):

        # Needed tp prevent a variable reference before assingment error.
        browser = None

        # This is the supported browser list(with the exception of the first browser)
        # and can be added to. Currently FireFox is not supported because it requires
        # a hack in order to get working. Calling FireFox as a root user is looked down
        # upon by Mozilla and they try to prevent this for the average user. Sorry for now!
        #
        # The first browser is there for convience so I dont have to write a seperate
        # method to check if the user proved browser path exists; It checks that browser first.
        # If it doesnt exist, then it will move on to the hard coded browsers in the list.
        browsers = [
            self._browser_,
            '/usr/bin/opera',
            '/opt/google/chome/chrome'
        ]

        for b in browsers: 
            if self.browser_exists(b) is not None:
                browser = re.match("(\/\w+)(.*\/)(\w+)",b).group(3)
                break
        if browser is None:
            logger.log("WARNING",
                "Browser not found and location functionality will not work.")
        elif browser == 'chrome':
            call([browser, "--user-data-dir="
                + str(fileOpts.root_directory()), "--no-sandbox", ""
                + self._website_
                + "?Email=" + self._email_])
        elif browser == 'opera':
            call([browser, "--user-data-dir="
                + str(fileOpts.root_directory()), "--no-sandbox", ""
                + self._website_
                + "?Email=" + self._email_])
            time.sleep(2)

class Database(object):

    def __init__(self):
        self.db_file = fileOpts.database_path()
        self.db      = sqlite3.connect(self.db_file)

        try:
            query = self.db.execute("select * from connected")
        except sqlite3.OperationalError:
            self.db.execute("CREATE TABLE connected(id integer primary key AUTOINCREMENT, "
                + "location_bool text not null, coordinates text not null, ip_addr text not null);")
            logger.log("INFO","Table(connected) does not exist, creating now.")

    def file_exists(self,file_name):
        return os.path.exists(file_name)

    def write_to_db(self,location_bool,coordinates,ip_addr):
        if location_bool is None or coordinates is None or ip_addr is None:
            return
        elif not re.search("true|false|NULL", location_bool, re.I|re.M):
            logger.log("ERROR", str(location_bool) + " is not a known mode.")
        elif not re.search("\A\((\d|\-\d)+\.\d+,\s(\d|\-\d)+\.\d+\)|NULL", coordinates, re.M | re.I):
            logger.log("ERROR", "Improper coordinate format -> " + str(coordinates) + ".")
        elif not re.search("\A\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}$|NULL", ip_addr, re.M|re.I):
            logger.log("ERROR", "Improper ip address format -> " + str(ip_addr) + ".")
        else:
            coor = re.sub("[\(\)]", "", str(coordinates))
            self.db.execute("insert into connected (location_bool, coordinates, ip_addr) "
                + "values(\""
                + str(location_bool) + "\", \""
                + str(coor) + "\", \""
                + str(ip_addr) + "\")")
            self.db.commit()

    def read_from_db(self,column):
        query = self.db.execute("select * from connected")
        for row in query:
            if column == 'location_bool' and row[1] is not None:
                return str(row[1])
            elif column == 'coordinates' and row[2] is not None:
                return str(row[2])
            elif column == 'ip_addr' and row[3] is not None:
                return str(row[3])
            else:
                logger.log("ERROR", "Not a known column or DB is empty.")
                return

    def update_db(self,column,value):
        if column is None or value is None:
            return
        try:
            if (self.read_from_db('location_bool') is None or
                self.read_from_db('coordinates') is None or 
                self.read_from_db('ip_addr') is None):
                    logger.log("ERROR", "You must write to the database first before updating!")
                    return
            elif re.search("true|false", value, re.I|re.M) and column == 'location_bool':
                self.db.execute("update connected set location_bool = \"" + value + "\"")
                self.db.commit()
            elif (re.search("\A(\d|\-\d)+\.\d+,\s(\d|\-\d)+\.\d+", value, re.M | re.I) and
                column == 'coordinates'):
                    self.db.execute("update connected set coordinates = \"" + value + "\"")
                    self.db.commit()
            elif (re.search("\A\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}$", value, re.M|re.I) and
                column == 'ip_addr'):
                    self.db.execute("update connected set ip_addr = \"" + value + "\"")
                    self.db.commit()
            else:
                logger.log("ERROR", str(column)
                    + " is not a known column for the connected table in the imagecapture db.")
                return
        except sqlite3.OperationalError:
            logger.log("ERROR", "The database is lock, could not add coordinates to DB.")

    def add_location_to_db(self,location_bool):
        try:
            if self.read_from_db('location_bool') is None:
                write_to_db(location_bool,'NULL','NULL')
                logger.log("INFO", "Writing location_bool to DB.")
            elif (self.read_from_db('location_bool') != location_bool and
                self.read_from_db('location_bool') is not None):
                    self.update_db('location_bool', location_bool)
                    logger.log("INFO", "Updating location_bool variable in DB.")
            else:
                return
        except sqlite3.OperationalError:
            call(['/usr/bin/rm', self.db_file])
            logger.log("ERROR", "The database is locked, could not add location_bool to DB.")
            pass

    def add_coordinates_to_db(self,coordinates):
        try:
            if self.read_from_db('coordinates') is None:
                self.write_to_db('NULL', coordinates,'NULL')
                logger.log("INFO", "Writing coordinates to DB.")
            elif (not self.read_from_db('coordinates') == coordinates
                and self.read_from_db('coordinates') is not None):
                    self.update_db('coordinates', ip_addr)
                    logger.log("INFO", "Updating coordinates variable in DB.")
            else:
                return
        except sqlite3.OperationalError:
            call(['/usr/bin/rm', self.db_file])
            logger.log("ERROR", "The database is locked, could not add coordinates to DB.")
            pass

    def add_ip_to_db(self,ip_addr):
        try:
            if self.read_from_db('ip_addr') is None:
                self.write_to_db('NULL','NULL', ip_addr)
                logger.log("INFO", "Writing ip_addr to DB.")
            elif (self.read_from_db('ip_addr') != ip_addr and
                self.read_from_db('ip_addr') is not None):
                    self.update_db('ip_addr', ip_addr)
                    logger.log("INFO", "Updating ip_addr variable in DB.")
            else:
                return
        except sqlite3.OperationalError:
            call(['/usr/bin/rm', self.db_file])
            logger.log("ERROR", "The database is locked, could not add IP address to DB.")
            pass

# This class is used to add/remove your username to/from the nopasswdlogin group.
# This group is looked at by the included pam modules that were custom tailored
# for this program. So if the user is in this group then your auth screen will
# automatically log you in. This is an optional feature that must be specified
# in the optparser via command line option.
class GraphicalDisplayManager(object):

    def add_to_group(self,user):
        os.system("sudo usermod -a -G nopasswdlogin " + str(user))

    def remove_from_group(self,user):
        os.system("sudo gpasswd -d " + str(user) + " nopasswdlogin")

    def user_present(self,user):
        with open("/etc/group", "r") as f:
            for line in f:
                nop = re.search("^nopasswdlogin.*(" + str(user) + ")", line)
                if nop is not None and nop:
                    return True
                elif nop is not None and not nop:
                    return False

    def auto_login_remove(self,autologin,user):
        if not autologin and self.user_present(user):
            logger.log("INFO", "Removing user " + str(user) + " from nopasswdlogin group.")
            self.remove_from_group(user)
        elif not autologin and not self.user_present(user):
            logger.log("WARN", "Cannot remove user " + str(user)
                + " from the nopasswdlogin group because they are not present.")
        elif not autologin and config_dict[0]['location'][0]:
            logger.log("WARN", "Cannot remove user " + str(user)
                + " from nopasswdlogin group while using the location feature.")

    def clear_auto_login(self,clear,user):
        if not clear:
            return
        elif len(sys.argv) > 2 and clear:
            logger.log("ERROR", "Too many arguments for clear given. Exiting now.")
            sys.exit(0)
        elif clear and self.user_present(user):
            logger.log("INFO", "Removing user " + str(user) + " from group nopasswdlogin")
            self.remove_from_group(user)
            sys.exit(0)
        elif clear and not self.user_present(user):
            logger.log("WARN", "Username " + str(user) + " is not in nopasswdlogin group.")
            sys.exit(0)

    def auto_login(self,autologin,user):
        if autologin:
            logger.log("INFO", "Automatically logging you in now.")
            self.add_to_group(user)

# This class returns user name you logged in with. This is used a lot in 
# this program especially in the GraphicalDisplayManager class. In that class 
# it allows this program to add/remove your username from the nopasswordlogin 
# group. See the GraphicalDisplayManager class for further explaination.
class User(object):

    @staticmethod
    def name():
        comm = subprocess.Popen(["users"], shell=True, stdout=subprocess.PIPE)
        if comm is not None:
            return re.search("(\w+)", str(comm.stdout.read())).group()
        logger.log("WARN", "The users command is not working properly. "
            + "This could break imagecapture's functionality!")
        return 'root'
    
class Net(object):

    @staticmethod
    def connected():
        try:
            urllib2.urlopen('http://www.google.com', timeout=1)
            return True
        except urllib2.URLError:
            return False

    # Returns your mac address. I will send this along with the other data
    # to better tie the data into the laptop definitively proving it's yours.
    @staticmethod
    def get_hardware_address(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
        return ':'.join(['%02x' % ord(char) for char in info[18:24]])

class Version(object):

    @staticmethod
    def python():
        python_version = re.search('\d\.\d', str(sys.version), re.I | re.M)
        if python_version is not None:
            return python_version.group()
        return "None"

class FileOpts(object):

    def root_directory(self):
        return "/home/" + str(User.name()) + "/.imagecapture"

    def picture_directory(self):
        return str(self.root_directory()) + "/pictures"

    def picture_path(self):
        return str(self.picture_directory()) + '/capture.png'

    def database_path(self):
        return str(self.root_directory()) + '/imagecapture.db'

    def file_exists(self,file_name):
        return os.path.isfile(file_name)

    def create_file(self,file_name):
        if not self.file_exists(file_name):
            open(file_name, 'w')

    def dir_exists(self,dir_path):
        return os.path.isdir(dir_path)

    def mkdir_p(self,dir_path):
        try:
            os.makedirs(dir_path)
        except OSError as e:
            if e.errno == errno.EEXIST and self.dir_exists(dir_path):
                pass
            else:
                raise

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option("-e", "--email",
        dest='email', default="example@gmail.com",
        help="E-mail address to send notofications to.")
    parser.add_option("-p", "--password",
        dest='password', default="password",
        help="Password used to sign-in to your E-mail account.")
    parser.add_option("-V", "--video",
        dest='video', default=0,
        help="Specify camera location.")
    parser.add_option("-v", "--verbose",
        dest='verbose', action="store_true", default=False,
        help="Print the options passed to ImageCapturePy.")
    parser.add_option("-P", "--port",
        dest='port', default=587,
        help="E-mail port defaults to 587 if not specified.")
    parser.add_option("-a", "--attempts",
        dest='attempts', default=3,
        help="Number of failed attempts defaults to 3.")
    parser.add_option("-L", "--location",
        dest='location', action="store_true", default=False,
        help="Enable location capturing.")
    parser.add_option("-U", "--persistent-location",
        dest='persistentlocation', action="store_true", default=False,
        help="Run location capturing routine everytime the computer is powered on.")
    parser.add_option("-l", "--log-file",
        dest='logfile',
        help="Log file for program to tail. There is no default and this option is mandatory!")
    parser.add_option("-c", "--enable-cam",
        dest='enablecam', action="store_true", default=False,
        help="Enable cam capture of intruder.")
    parser.add_option("-A", "--auto-login",
        dest='autologin', action="store_true",  default=False,
        help="Auto login user after no of failed attempts.")
    parser.add_option("-w", "--website",
        dest='website', default='https://imagecapturepy.herokuapp.com/index.html',
        help="Use alternate website to capture location.")
    parser.add_option("-X", "--clear-autologin",
        dest='clearautologin', action="store_true", default=False,
        help="Remove autologin. Must be root to use this feature.")
    parser.add_option("-s", "--allow-sucessful",
        dest='allowsucessful', action="store_true", default=False,
        help="Run ImageCapture even if login is sucessful.")
    parser.add_option("-B", "--browser",
        dest="browser", default="/opt/google/chrome/chrome",
        help="Select the browser used to grab geolocation data.")
    parser.add_option("-C", "--config-file",
        dest="configfile", default='',
        help="Configuration file path.")
    (options, args) = parser.parse_args()

    logger   = Logging()

    # These strings are used to compare against the command line args passed.
    # It could have been done with an action but default values were used instead.
    # These strings are coupled with their respective counterpart in the config_dist
    # data structure declared below.

    email              = '(e|--email)'
    password           = '(p|--password)'
    video              = '(V|--video)'
    verbose            = '(v|--verbose)'
    port               = '(P|--port)'
    attempts           = '(a|--attempts)'
    location           = '(L|--location)'
    persistentlocation = '(U|--persistent-location)'
    logfile            = '(l|--log-file)'
    enablecam          = '(c|--enable-cam)'
    autologin          = '(A|--auto-login)'
    website            = '(w|--website)'
    clearautologin     = '(X|--clear-autologin)'
    allowsucessful     = '(s|--allow-sucessful)'
    browser            = '(B|--browser)'
    configfile         = '(C|--config-file)'

    # Easiest way to share variables between clases without wanting to 
    # chop my computer up with an fucking axe! The key is used for reference
    # while the first value is reserved for config files values and if they 
    # are blank then they are filled in with the 2nd values value. The array 
    # inside the array after the dictionary declaration is reserved for when 
    # the config file option is passed but an option has no value. That key
    # name is stored in this array.

    config_dict = [{
        'email': ['', options.email, email],
        'password': ['', options.password, password],
        'video': ['', options.video, video],
        'verbose': ['', options.verbose, verbose],
        'port': ['', options.port, port],
        'attempts': ['', options.attempts, attempts],
        'location': ['', options.location, location],
        'persistentlocation': ['', options.persistentlocation, persistentlocation],
        'logfile': ['', options.logfile, logfile],
        'enablecam': ['', options.enablecam, enablecam],
        'autologin': ['', options.autologin, autologin],
        'website': ['', options.website, website],
        'clearautologin': ['', options.clearautologin, clearautologin],
        'allowsucessful': ['', options.allowsucessful, allowsucessful],
        'browser': ['', options.browser, browser],
        'configfile': ['', options.configfile, configfile]
    }, []]

    # This will recursivley check for and or
    # create the program's directory tree structure.
    # home/user/.imagecapture/pictures/capture.png

    fileOpts = FileOpts()

    if not fileOpts.file_exists(fileOpts.picture_path()):
        if not fileOpts.dir_exists(fileOpts.picture_directory()):
            if not fileOpts.dir_exists(fileOpts.root_directory()):
                fileOpts.mkdir_p(fileOpts.root_directory())
                fileOpts.mkdir_p(fileOpts.picture_directory())
                fileOpts.create_file(fileOpts.picture_path())
            fileOpts.mkdir_p(fileOpts.picture_directory())
            fileOpts.create_file(fileOpts.picture_path())            
        fileOpts.create_file(fileOpts.picture_path())

    if not fileOpts.file_exists('/var/log/imagecapture.log'):
        fileOpts.create_file('/var/log/imagecapture.log')

    database = Database()
    gdm      = GraphicalDisplayManager()

    ImageCapture(config_dict).main()
