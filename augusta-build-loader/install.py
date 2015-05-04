#!/usr/bin/python

import sys
import os
import subprocess

PROG_NAME = 'augusta-loader'
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
OSBIN_DIR = '/usr/local/bin'

# Backported from Python 2.7 as it's implemented as pure python on stdlib.
def check_output(*popenargs, **kwargs):
    
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output

def check_root_uid():
    if os.geteuid() != 0:
        print >> sys.stderr, "You need to have root privilege to install '%s'." % PROG_NAME
        print >> sys.stderr, "exiting"
        sys.exit(1)

if __name__ == "__main__":
    
    check_root_uid()
    
    print "Install Augusta Build Loader ..."
    print ''
    
    print "Installation directory: %s" % BASE_DIR
    
    loader_bin_path = os.path.join(BASE_DIR, 'bin', 'augusta-loader.py')
    subprocess.call("chmod +x %s" % loader_bin_path, shell=True)
    
    if os.path.exists(loader_bin_path):
        print "Script path: %s" % loader_bin_path
    else:
        print "Script %s not found" % loader_bin_path
        sys.exit(1)

    build_dir = os.path.join(BASE_DIR, 'build')
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    profile_dir = os.path.join(BASE_DIR, 'profiles')
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    
    print ''
    
    grep_result = check_output("grep %s %s || true" % (loader_bin_path, '/etc/sudoers'), shell=True)
    
    if len(grep_result.splitlines()) > 0:
        print "The sudo configuration for build loader already exists in /etc/sudoers ... skip"
        print "You can edit the sudo configuration manually via 'visudo' command."
    else:
        sudo_rule = "%%libvirtd ALL=(root) NOPASSWD: %s" % loader_bin_path
        subprocess.call('echo "%s" >> /etc/sudoers' % sudo_rule, shell=True)
        print "sudo configuration added."
    print ''
    
    print "The users in 'libvirtd' group should have the privilege to run augusta-loader."
    print "Please add your user account into 'libvirtd' group.";
    print "It is NOT recommended to login as 'root'!"
    print ''
    
    script_bin_path = os.path.join(OSBIN_DIR, 'augusta-loader')
    
    if os.path.exists(script_bin_path):
        os.unlink(script_bin_path)
            
    with open(script_bin_path, 'w') as fp:
        fp.write("#!/bin/sh -e\n")
        fp.write("\n")
        fp.write("sudo %s $@\n" % loader_bin_path)
        
    subprocess.call("chmod +x %s" % script_bin_path, shell=True)
    
    print "System script %s added." % script_bin_path
    print ''
    
    print "Augusta Build Loader installed successfully."
    print "Please type 'augusta-loader --help' for more information."     
        
