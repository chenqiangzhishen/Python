#!/usr/bin/python
#
# Augusta Build Loader - the build image loader for IBM Augusta project
#
# Copyright 2014  IBM Corp.
# Chen Qiang <qchensh@cn.ibm.com>
#

import sys
import os
import textwrap
import urllib
import urllib2
import re
import subprocess
import shutil
import time

# customized configuration 
#MIRROR_URL = 'https://rtpgsa.ibm.com/projects/a/augusta/0.1/official/'
MIRROR_URL = 'http://9.115.253.12/pub/augusta/build/nightly/'
#MIRROR_URL = 'http://9.115.235.138/0.1/official/'
#BANDOL_MIRROR_URL = 'http://9.115.235.138/1.0/official/'
TEVEL_MIRROR_URL = 'http://9.115.253.12/pub/augusta/build/1.0/'
BANDOL_MIRROR_URL = 'http://9.115.253.12/pub/augusta/build/2.0/'
STORAGE_DIR = '/vmstorage'
VM_MEM = 2048
VM_CPU = 2
VM_BRIDGE = 'br0'

# program constants
PROG_NAME = 'augusta-loader'
PROG_VERSION = '1.2'
BIN_DIR = os.path.dirname(os.path.realpath(__file__))
BASE_DIR = os.path.dirname(BIN_DIR)
CONFIG_DIR = os.path.join(BASE_DIR, 'profiles')
BUILD_DIR = os.path.join(BASE_DIR, 'build')
IMG_MOUNT = os.path.join(BASE_DIR, 'mnt')
PIDFILE = '/tmp/augusta-loader.pid'
CHENAS_STREAM = '0.1'
TEVEL_STREAM = '1.0'
BANDOL_STREAM = '2.0'

# additional libraries
sys.path.append(os.path.join(BASE_DIR, 'lib'))
import argparse

script_locked = False

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

def get_build_list(mirror_url):
    pattern = r'<a href="[^?/\s].*?">(.*?)/</a>'
    
    dir_html = urllib2.urlopen(mirror_url).read()

    build_list = re.findall(pattern, dir_html)

    return build_list

def get_profile_names(users, strict=True):
    config_dir = CONFIG_DIR;
    
    predefined = os.listdir(config_dir);
    
    if 'all' in users:
        name_list = predefined
    else:
        name_list = list()
        for u in users:
            if u in predefined:
                name_list.append(u)
            elif strict:
                raise Exception("no such profile '%s', try to use the '--adhoc' option if available" % u)
            else:
                name_list.append(u)

    return name_list

def get_profile_list(users=['all']):
    name_list = get_profile_names(users)

    profiles = list()
    for basename in name_list:
        info = get_profile_info(basename)
        if info:
            profiles.append(info)
        
    return profiles

def get_profile_info(name):
    config_dir = CONFIG_DIR;

    path = os.path.join(config_dir, name)
        
    if (os.path.isdir(path)):
        info = dict()
        info['name'] = name

        ifcfg_path = os.path.join(path, 'ifcfg-eth0')
        ifcfg_info = dict()
        with open(ifcfg_path, 'r') as fp:
            ifcfg_info = dict(line.strip().split('=') for line in fp.readlines())
            
        info['ipaddr'] = ifcfg_info['IPADDR']
        info['netmask'] = ifcfg_info['NETMASK']

        return info

    return None

def get_virt_list(user=None, all=False):
    if all:
        cmdline = "virsh list --all | grep Augusta-* | awk '{print $2}'"
    else:
        cmdline = "virsh list | grep Augusta-* | awk '{print $2}'"

    stdout = check_output(cmdline, shell=True)

    vm_list = list()

    for line in stdout.splitlines():
        vm_name = line.strip()
        if user != None:
            if vm_name.endswith(user):
                vm_list.append(vm_name)
        else:
            if vm_name != '':
                vm_list.append(vm_name)

    vm_list.sort(reverse=True)

    return vm_list

def get_active_vm_list(user=None):
    return get_virt_list(user, False)

def get_all_vm_list(user=None):
    return get_virt_list(user, True)
            
def cmd_list_build(stream):
    mirror_url = MIRROR_URL
    build_dir = BUILD_DIR
    
    if stream is not None:
        if BANDOL_STREAM in stream:
            mirror_url = BANDOL_MIRROR_URL
        if TEVEL_STREAM in stream:
            mirror_url = TEVEL_MIRROR_URL
    
    build_list = get_build_list(mirror_url)

    print 'Retrieving list from %s\n' % mirror_url

    template = '{0:<25} {1:<16}'

    print template.format('Build Name', 'Location')
    print '-' * 42

    for build_name in build_list:
        build_img = os.path.join(build_dir, build_name, 'augusta.qcow2')
        if os.path.isfile(build_img):
            location = 'local/server' 
        else:
            location = 'server'
            
        print template.format(build_name, location)

def cmd_list_profile():
    profile_list = get_profile_list()
    running_instances = get_active_vm_list()
    installed_instances = get_all_vm_list()

    template = '{0:<10} {1:<38} {2:<10} {3:<15}'
    
    print template.format('Profile', 'Instance', 'State', 'IP')
    print '-' * 76
 
    for profile in profile_list:
        name = profile['name']
        instance = ''
        state = ''
        ipaddr = profile['ipaddr']

        for vm_name in running_instances:
            if vm_name.endswith(name):
                instance = vm_name
                state = 'running'
                break
        else:
            for vm_name in installed_instances:
                if vm_name.endswith(name):
                    instance = vm_name
                    state = 'off'

        print template.format(name, instance, state, ipaddr)

def cmd_install_virtapp(users, stream, build=None, adhoc=False, develop_mode=False):
    mirror_url = MIRROR_URL
    build_dir = BUILD_DIR
    config_dir = CONFIG_DIR
    storage_dir = STORAGE_DIR
    img_mount = IMG_MOUNT

    if build is not None:
        if build.startswith(BANDOL_STREAM):
            mirror_url = BANDOL_MIRROR_URL
        if build.startswith(TEVEL_STREAM):
            mirror_url = TEVEL_MIRROR_URL

    if stream is not None:
        if BANDOL_STREAM in stream:
            mirror_url = BANDOL_MIRROR_URL
        if TEVEL_STREAM in stream:
            mirror_url = TEVEL_MIRROR_URL
    
    if not adhoc:
        profile_names = get_profile_names(users)
    else:
        all_profiles = get_profile_names(['all'])
        for user in users:
            if user == 'all':
                raise Exception("'all' is not invalid for the ad-hoc installation")
            elif user in all_profiles:
                raise Exception("%s is a pre-defined profile, in conflict with the '--adhoc' option" % user)
        profile_names = users
    
    build_list = get_build_list(mirror_url)
    build_list.sort(reverse=True)
    
    if len(build_list) == 0:
        raise Exception("no build available from %s" % mirror_url)
    
    if build is None:
        build_name = build_list[0]
    elif not build in build_list:
        raise Exception("build '%s' is not available" % build)
    else:
        build_name = build
    
    build_url = mirror_url + "%s/KVM/augusta.qcow2" % build_name  
    build_img = os.path.join(build_dir, build_name, 'augusta.qcow2')
    local_img = os.path.join(storage_dir, build_name + '-template.raw')
    vm_name = None
    vm_disk = None
    
    head_template = "{0:<16} {1:<36}"
    print head_template.format("Build Mirror:", mirror_url)
    print head_template.format("Build Name:", build_name)
    print head_template.format("Profiles:", profile_names)
    print ''
    
    if not os.path.exists(build_img):
        try:
            dl_dir = os.path.dirname(build_img)
            if not os.path.exists(dl_dir):
                os.makedirs(dl_dir)
            print "Get %s ..." % build_url,
            sys.stdout.flush()
            urllib.urlretrieve(build_url, build_img)
            print 'done'
            print ''
        except (KeyboardInterrupt, Exception) as err:
            print ''
            shutil.rmtree(dl_dir, ignore_errors=True)
            raise err
            
    try:
        if adhoc == False:
            print 'Converting build to local image ...',
            sys.stdout.flush()
            ret = subprocess.call("qemu-img convert -f qcow2 -O raw %s %s" % (build_img, local_img), shell=True)
            if ret == 0:
                print 'done'
            else:
                print ''
                raise Exception('failed to convert build image.')
        
        for user in profile_names:
            profile = get_profile_info(user)
            vm_list = get_all_vm_list(user)
            active_list = get_active_vm_list(user)
            profile_dir = os.path.join(config_dir, user)
            gateway_config_dir = os.path.join(img_mount, 'etc/sysconfig')
            local_config_dir = os.path.join(img_mount, 'etc/sysconfig/network-scripts')
            start_server_path = os.path.join(img_mount, 'opt/ibm/augusta/bin/start-server.sh')
                    
            vm_name = 'Augusta-%s-%s' % (build_name, user)
            vm_disk = os.path.join(storage_dir, vm_name + '.qcow2')
                
            if vm_name in vm_list:
                print "%s is up to date." % vm_name
                continue
            
            if os.path.exists(profile_dir):
                print 'Making KVM image %s ...' % vm_disk
                
                kpartx_out = check_output("kpartx -av -s %s" % local_img, shell=True)
                part_list = re.findall("add map (loop\d+p\d+)", kpartx_out)
                if len(part_list) > 0:
                    root_block = '/dev/mapper/' + part_list[0]
                else:
                    raise Exception("Root partition not found")
                
                print 'Block device: ' + root_block
                if os.path.exists(root_block) == False:
                    raise Exception("no device %s" % root_block)
                
                if not os.path.exists(img_mount):
                    os.makedirs(img_mount)

                ret = subprocess.call("mount -o loop %s %s" % (root_block, img_mount), shell=True)
                if ret != 0:
                    raise Exception("unable to mount %s" % root_block)
                
                ifcfg_path = os.path.join(profile_dir, 'ifcfg-eth0')
                route_path = os.path.join(profile_dir, 'network')
                
                if os.path.isfile(ifcfg_path):
                    shutil.copy(ifcfg_path, local_config_dir)
                
                if os.path.isfile(route_path):
                    shutil.copy(route_path, gateway_config_dir)

                if develop_mode:
                    print "Develop mode: changing start-server.sh"
                    print "sed -i 's/ASPECTJ_JAR/ASPECTJ_JAR -Dcom.ibm.sysx.xhmc.discovery.management.skipLDAPConfig=true/' %s" % start_server_path
                    subprocess.call("sed -i 's/ASPECTJ_JAR/ASPECTJ_JAR -Dcom.ibm.sysx.xhmc.discovery.management.skipLDAPConfig=true/' %s" % start_server_path, shell=True)
                
                subprocess.call("sync", shell=True)
                time.sleep(5)

                ret = subprocess.call("umount %s" % img_mount, shell=True)
                if ret != 0:
                    raise Exception("unable to umount %s" % img_mount)
                
                time.sleep(5)
                ret = subprocess.call("kpartx -d %s" % local_img, shell=True)
                if ret != 0:
                    raise Exception("unable to disconnect %s" % local_img)
                
                ret = subprocess.call("qemu-img convert -f raw -O qcow2 %s %s" % (local_img, vm_disk), shell=True)
                if ret != 0:
                    raise Exception("failed to create KVM image")
                
                print 'KVM image %s modified successfully.' % os.path.basename(vm_disk)
                print ''
            else:
                print 'Making KVM image %s ...' % vm_disk,
                sys.stdout.flush()
                shutil.copy(build_img, vm_disk)
                print 'done'                
            
            if len(active_list) > 0:
                print "Shutting down old instances ...",
                sys.stdout.flush()
                for vm in active_list:
                    subprocess.call("virsh destroy %s >/dev/null 2>&1" % vm, shell=True)
                print 'done'
                    
            virt_args = {'vm_name': vm_name,
                         'vm_mem': VM_MEM,
                         'vm_cpu': VM_CPU,
                         'vm_bridge': VM_BRIDGE,
                         'vm_disk': vm_disk}
            
            print 'Install %s ...' % vm_name,
            sys.stdout.flush()
            ret = subprocess.call("virt-install --import -n %(vm_name)s -r %(vm_mem)d --vcpus=%(vm_cpu)d -v --graphics vnc,listen=0.0.0.0 --disk path=%(vm_disk)s,format=qcow2 --network bridge=%(vm_bridge)s --noautoconsole --noreboot >/dev/null 2>&1" % 
                            virt_args, shell=True)
            if ret != 0:
                raise Exception("failed to install %s" % vm_name)
                        
            subprocess.call("virsh snapshot-create-as --domain %(vm_name)s --name init-build --description 'Initial Augusta Build' >/dev/null 2>&1" % 
                            virt_args, shell=True)
            subprocess.call("virsh start %(vm_name)s >/dev/null 2>&1" % 
                            virt_args, shell=True)
            
            print 'done'
            print ''
            # end of for
            
        if not adhoc:
            os.remove(local_img)
    except (KeyboardInterrupt, Exception) as err:
        # clean-up operations
        print 'Cleaning up ...'
        
        subprocess.call("sync", shell=True)
        time.sleep(5)
        
        subprocess.call("umount %s >/dev/null 2>&1" % img_mount, shell=True)
        subprocess.call("kpartx -d %s >/dev/null 2>&1" % local_img, shell=True)
        
        if local_img and os.path.exists(local_img):
            os.remove(local_img)
            
        if vm_disk and os.path.exists(vm_disk):
            os.remove(vm_disk)
            
        raise err
                    
def cmd_start_virtapp(users, build=None):

    profile_names = get_profile_names(users, False)

    for user in profile_names:
        vm_list = get_all_vm_list(user)
        active_list = get_active_vm_list(user)
        
        if len(vm_list) == 0:
            raise Exception("no build installed for '%s'" % user)
        
        if build is None:
            vm_name = vm_list[0]
        else:
            vm_name = 'Augusta-%s-%s' % (build, user)
            
        if not vm_name in vm_list:
            raise Exception("%s not found" % vm_name)
        
        if vm_name in active_list:
            print "%s is already running" % vm_name
            continue
            
        print "Shutting down old instances ...",
        sys.stdout.flush()
        for vm in active_list:
            subprocess.call("virsh destroy %s >/dev/null 2>&1" % vm, shell=True)
        print 'done'
        
        print 'Starting %s ...' % vm_name
        
        subprocess.call("virsh start %s >/dev/null 2>&1" % vm_name, shell=True)

def cmd_shutdown_virtapp(users, build=None):

    profile_names = get_profile_names(users, False)

    for user in profile_names:
        vm_list = get_all_vm_list(user)
        active_list = get_active_vm_list(user)
        
        if len(vm_list) == 0:
            raise Exception("no build installed for '%s'" % user)
        
        if build is None:
            vm_name = vm_list[0]
        else:
            vm_name = 'Augusta-%s-%s' % (build, user)
            
        if not vm_name in vm_list:
            raise Exception("%s not found" % vm_name)
        
        if not vm_name in active_list:
            print "%s is not started" % vm_name
            continue
    
        print 'Shutting down %s ...' % vm_name,
        sys.stdout.flush()
        
        ret = subprocess.call("virsh destroy %s" % vm_name, shell=True)
        if ret != 0:
            raise Exception('unable to shutdown %s' % vm_name)
        
        print 'done'

def cmd_revert_virtapp(users, build=None):
    snapshot = 'init-build'

    profile_names = get_profile_names(users, False)

    for user in profile_names:
        vm_list = get_all_vm_list(user)
                
        if len(vm_list) == 0:
            raise Exception("no build installed for '%s'" % user)
        
        if build is None:
            vm_name = vm_list[0]
        else:
            vm_name = 'Augusta-%s-%s' % (build, user)
            
        if not vm_name in vm_list:
            raise Exception("%s not found" % vm_name)
        
        print "Reverting %s to '%s':" % (vm_name, snapshot)
        
        ret = subprocess.call("virsh snapshot-revert %s %s >/dev/null 2>&1" % (vm_name, snapshot), shell=True)
        if ret != 0:
            print ''
            raise Exception('unable to revert %s' % vm_name)
        
        print "%s reverted." % vm_name
        
        active_list = get_active_vm_list(user)
        
        print 'Starting %s ...' % vm_name,
        sys.stdout.flush()
        
        for vm in active_list:
            subprocess.call("virsh destroy %s >/dev/null 2>&1" % vm, shell=True)

        subprocess.call("virsh start %s >/dev/null 2>&1" % vm_name, shell=True)
        
        print 'done'
        
def cmd_delete_virtapp(users, build):
    storage_dir = STORAGE_DIR

    profile_names = get_profile_names(users, False)

    for user in profile_names:
        vm_list = get_all_vm_list(user)
        active_list = get_active_vm_list(user)
        
        vm_name = 'Augusta-%s-%s' % (build, user)
            
        if not vm_name in vm_list:
            raise Exception("%s not found" % vm_name)
        
        print 'Deleting instance %s:' % vm_name 
        
        if vm_name in active_list:
            subprocess.call("virsh destroy %s" % vm_name, shell=True)
                
        subprocess.call("virsh snapshot-delete --current %s" % vm_name, shell=True)
        subprocess.call("virsh undefine %s" % vm_name, shell=True)

        for file in os.listdir(storage_dir):
            rootname, ext = os.path.splitext(file)
            if rootname == vm_name:
                disk_path = os.path.join(storage_dir, file)
                os.remove(disk_path)
                print '%s deleted.' % disk_path
                print ''

def cmd_clean_vm(users, keep, clean_all=False):
    storage_dir = STORAGE_DIR

    profile_names = get_profile_names(users, False)

    for user in profile_names:
        vm_list = get_all_vm_list(user)
        active_list = get_active_vm_list(user)
        
        if clean_all:
            delete_list = vm_list
        else:
            delete_list = vm_list[keep:]
        
        for vm_name in delete_list:            
            print 'Deleting instance %s:' % vm_name 
            
            if vm_name in active_list:
                subprocess.call("virsh destroy %s" % vm_name, shell=True)
                
            subprocess.call("virsh snapshot-delete --current %s" % vm_name, shell=True)
            subprocess.call("virsh undefine %s" % vm_name, shell=True)

            for file in os.listdir(storage_dir):
                rootname, ext = os.path.splitext(file)
                if rootname == vm_name:
                    disk_path = os.path.join(storage_dir, file)
                    os.remove(disk_path)
                    print '%s deleted.' % disk_path
                    print ''
        
def cmd_clean_build(keep, clean_all=False):
    build_dir = BUILD_DIR
    
    build_list = os.listdir(build_dir)
    build_list.sort(reverse=True)
    
    if clean_all:
        delete_list = build_list
    else:
        delete_list = build_list[keep:]
        
    for build_name in delete_list:
        dl_dir = os.path.join(build_dir, build_name)
        print 'Deleting %s ...' % dl_dir,
        sys.stdout.flush()
        shutil.rmtree(dl_dir)
        print 'done'
        
def cmd_add_profile(user, ipaddr, netmask, gateway):
    config_dir = CONFIG_DIR;

    dir_path = os.path.join(config_dir, user)
    
    if os.path.exists(dir_path):
        raise Exception("profile %s exists" % user)
    
    os.makedirs(dir_path)
    
    ifcfg_path = os.path.join(dir_path, 'ifcfg-eth0')
    with open(ifcfg_path, 'w') as ifcfg_fp:
        ifcfg_fp.write('DEVICE=eth0\n')
        ifcfg_fp.write('BOOTPROTO=static\n')
        ifcfg_fp.write('ONBOOT=yes\n')
        ifcfg_fp.write('IPADDR=%s\n' % ipaddr)
        ifcfg_fp.write('NETMASK=%s\n' % netmask)
        ifcfg_fp.write('STARTMODE=auto\n')
    
    route_path = os.path.join(dir_path, 'network')
    with open(route_path, 'w') as route_fp:
        route_fp.write('NETWORKING=yes\n')
        route_fp.write('GATEWAY=%s' % gateway)
    
    print "Profile %s added successfully." % user
    
def cmd_del_profile(user):
    config_dir = CONFIG_DIR;

    dir_path = os.path.join(config_dir, user)
    
    if not os.path.exists(dir_path):
        raise Exception("profile %s not found" % user)
    
    cmd_clean_vm([user], 0, True)
    
    shutil.rmtree(dir_path)
    
    print "Profile %s deleted." % user
                
def parse_args():
    root_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        usage=textwrap.dedent('''\
                %(prog)s command [options]
                       %(prog)s install|revert|start|shutdown|delete [options] all|user1 [user2 ...]
                       %(prog)s add-profile [options] user ipaddr netmask gateway
                       %(prog)s del-profile [options] user'''),
        description=textwrap.dedent('''\
            The build image loader for IBM Augusta project.
            
            See "%(prog)s command --help" for more details.
            
            commands:
                install - Install build images
                start - Start VM instance
                shutdown - Shutdown VM instance
                revert - Revert VM instance to initial state
                delete - Delete the VM instance of a build
                clean-vm - Delete obsolete VM instances
                clean-build - Delete obsolete build images
                list-build - List available build numbers
                list-profile - List available profile names
                add-profile - Add a profile with a static IP address
                del-profile - Delete a profile configuration
        '''),
        add_help=False)
    root_parser.add_argument('-v', '--version',
                             dest='version', action='store_true',
                             help='version information')
    root_parser.add_argument('-h', '--help',
                             dest='help', action='store_true',
                             help='this help')
    root_parser.add_argument('command',
                             nargs='?',
                             help='command to execute')
    root_parser.add_argument('args',
                             nargs=argparse.REMAINDER,
                             help='command arguments')

    virtapp_parser = argparse.ArgumentParser(usage='%(prog)s [options] all|profile1 [profile2 ...]',
                                             add_help=False)
    virtapp_parser.add_argument('users',
                                metavar='user', nargs='+',
                                help='the profile names for VM instances') 
    install_parser = argparse.ArgumentParser(prog='install', parents=[virtapp_parser],
                                             description="Install build images")
    install_parser.add_argument('-b', '--build',
                                metavar='BUILD_NUM',
                                help='use the image of this build number')
    install_parser.add_argument('-a', '--adhoc',
                                dest='adhoc', action='store_true',
                                help='install a ad-hoc VM instance using DHCP if the profile is undefined')
    install_parser.add_argument('-d', '--develop',
                                 dest="develop_mode", action='store_true',
                                 help='Enable developer mode')
    install_parser.add_argument('-s', '--stream',
                               metavar='STREAM_NUM',
                               help='stream num could be 0.1 or 1.0')
    start_parser = argparse.ArgumentParser(prog='start', parents=[virtapp_parser],
                                           description="Start VM instance")
    start_parser.add_argument('-b', '--build',
                              metavar='BUILD_NUM',
                              help='use the image of this build number')
    shutdown_parser = argparse.ArgumentParser(prog='shutdown', parents=[virtapp_parser],
                                              description="Shutdown VM instance")
    shutdown_parser.add_argument('-b', '--build',
                                 metavar='BUILD_NUM',
                                 help='use the image of this build number')
    revert_parser = argparse.ArgumentParser(prog='revert', parents=[virtapp_parser],
                                            description="Revert VM instance to initial state")
    revert_parser.add_argument('-b', '--build',
                               metavar='BUILD_NUM',
                               help='use the image of this build number')
    delete_parser = argparse.ArgumentParser(prog='delete', parents=[virtapp_parser],
                                            description="Delete the VM instance of a build")
    delete_parser.add_argument('-b', '--build',
                               metavar='BUILD_NUM', required=True,
                               help='use the image of this build number')
    clean_vm_parser = argparse.ArgumentParser(prog='clean-vm', parents=[virtapp_parser],
                                              description="Delete obsolete VM instances")
    clean_vm_parser.add_argument('--keep',
                                 dest="keep", metavar='NUMBER', type=int, default=1,
                                 help='the number of builds or instances to keep')
    clean_vm_parser.add_argument('--clean-all',
                                 dest="clean_all", action='store_true',
                                 help='clean all VM instances of one or more profiles')    
    common_parser = argparse.ArgumentParser(usage='%(prog)s [options]',
                                            add_help=False)
    clean_build_parser = argparse.ArgumentParser(prog='clean-build', parents=[common_parser],
                                                 description="Delete obsolete build images")
    clean_build_parser.add_argument('--keep',
                                    dest="keep", metavar='NUMBER', type=int, default=5,
                                    help='the number of builds or instances to keep')
    clean_build_parser.add_argument('--clean-all',
                                    dest="clean_all", action='store_true',
                                    help='clean all local build images')
    list_build_parser = argparse.ArgumentParser(prog='list-build', parents=[common_parser],
                                                description="List available build numbers")
    list_build_parser.add_argument('-s', '--stream',
                               metavar='STREAM_NUM',
                               help='stream num could be 0.1 or 1.0')
    list_profile_parser = argparse.ArgumentParser(prog='list-profile', parents=[common_parser],
                                                  description="List available profile names")

    profile_parser = argparse.ArgumentParser(add_help=False)
    add_profile_parser = argparse.ArgumentParser(parents=[profile_parser],
                                                 usage='%(prog)s [options] user ipaddr netmask gateway',
                                                 description="Add a profile with a static IP address")
    add_profile_parser.add_argument('user', help='profile name')
    add_profile_parser.add_argument('ipaddr', help='IP address')
    add_profile_parser.add_argument('netmask', help='subnet mask')
    add_profile_parser.add_argument('gateway', help='gateway IP address')
    del_profile_parser = argparse.ArgumentParser(parents=[profile_parser],
                                                 usage='%(prog)s [options] user',
                                                 description="Delete a profile configuration")
    del_profile_parser.add_argument('user', help='profile name')

    root_args = root_parser.parse_args()
    command = root_args.command
   
    if command is None:
        if root_args.help:
            root_parser.print_help()
            sys.exit(0)
        if root_args.version:
            print 'Augusta Build Loader %s' % PROG_VERSION
            sys.exit(0)
        else:
            root_parser.print_usage()
            print '%s: too few arguments' % PROG_NAME
            sys.exit(1)
    if command == 'install':
        cmd_args = install_parser.parse_args(root_args.args)
    elif command == 'start':
        cmd_args = start_parser.parse_args(root_args.args)
    elif command == 'shutdown':
        cmd_args = shutdown_parser.parse_args(root_args.args)
    elif command == 'revert':
        cmd_args = revert_parser.parse_args(root_args.args)
    elif command == 'delete':
        cmd_args = delete_parser.parse_args(root_args.args)
    elif command == 'clean-vm':
        cmd_args = clean_vm_parser.parse_args(root_args.args)
    elif command == 'clean-build':
        cmd_args = clean_build_parser.parse_args(root_args.args)
    elif command == 'list-build':
        cmd_args = list_build_parser.parse_args(root_args.args)
    elif command == 'list-profile':
        cmd_args = list_profile_parser.parse_args(root_args.args)
    elif command == 'add-profile':
        cmd_args = add_profile_parser.parse_args(root_args.args)
    elif command == 'del-profile':
        cmd_args = del_profile_parser.parse_args(root_args.args)
    else:
        root_parser.print_usage();
        print '%s: unrecognized command \'%s\'' % (PROG_NAME, command)
        sys.exit(1)
    
    return (command, cmd_args)

def lock_script():
    global script_locked
    
    pid = os.getpid()
    
    if os.path.exists(PIDFILE):
        print '%s process is already running, exiting' % PROG_NAME
        sys.exit(1)
    else:
        script_locked = True
        with open(PIDFILE, 'w') as fp:
            fp.write(str(pid))

def unlock_script():
    global script_locked
    
    if os.path.exists(PIDFILE):
        os.unlink(PIDFILE)
    
    script_locked = False

def check_root_uid():
    if os.geteuid() != 0:
        print >> sys.stderr, "You need to have root privilege to run this command."
        print >> sys.stderr, "Please try running this command again with 'sudo' or ask your system admin."
        print >> sys.stderr, "exiting"
        sys.exit(1)
        
def main():
    command, cmd_args = parse_args()
    
    if command == 'install':
        check_root_uid()
        lock_script()
        cmd_install_virtapp(cmd_args.users,
                            cmd_args.stream,
                          cmd_args.build,
                          cmd_args.adhoc,
                            cmd_args.develop_mode)
    elif command == 'start':
        lock_script()
        cmd_start_virtapp(cmd_args.users,
                          cmd_args.build)
    elif command == 'shutdown':
        lock_script()
        cmd_shutdown_virtapp(cmd_args.users,
                          cmd_args.build)
    elif command == 'revert':
        lock_script()
        cmd_revert_virtapp(cmd_args.users,
                          cmd_args.build)
    elif command == 'delete':
        check_root_uid()
        lock_script()
        cmd_delete_virtapp(cmd_args.users,
                          cmd_args.build)
    elif command == 'clean-vm':
        check_root_uid()
        lock_script()
        cmd_clean_vm(cmd_args.users,
                     cmd_args.keep,
                     cmd_args.clean_all)
    elif command == 'clean-build':
        check_root_uid()
        lock_script()
        cmd_clean_build(cmd_args.keep,
                        cmd_args.clean_all)
    elif command == 'list-build':
        cmd_list_build(cmd_args.stream);
    elif command == 'list-profile':
        cmd_list_profile();
    elif command == 'add-profile':
        check_root_uid()
        lock_script()
        cmd_add_profile(cmd_args.user,
                        cmd_args.ipaddr,
                        cmd_args.netmask,
                        cmd_args.gateway)
    elif command == 'del-profile':
        check_root_uid()
        lock_script()
        cmd_del_profile(cmd_args.user)

if __name__ == "__main__":
    try:
        main()
    except SystemExit, sys_e:
        sys.exit(sys_e.code)
    except KeyboardInterrupt:
        print >> sys.stderr, "Aborted at user request"
        sys.exit(1)
    except Exception as err:
        print >> sys.stderr, PROG_NAME + ": ", err
        sys.exit(1)
    finally:
        if script_locked:
            unlock_script()
