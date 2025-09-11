[main]
cachedir=/tmp/yum
keepcache=0
debuglevel=2
logfile=/var/log/yum.log
exactarch=1
obsoletes=1
gpgcheck=0
plugins=1
installonly_limit=3
reposdir=/etc/yum.repos.d.xs

#  This is the default, if you make this bigger yum won't see if the metadata
# is newer on the remote and so you'll "gain" the bandwidth of not having to
# download the new metadata and "pay" for it by yum not having correct
# information.
#  It is esp. important, to have correct metadata, for distributions like
# Fedora which don't keep old packages around. If you don't like this checking
# interupting your command line usage, it's much better to have something
# manually check the metadata once an hour (yum-updatesd will do this).
# metadata_expire=90m

# PUT YOUR REPOS HERE OR IN separate files named file.repo
# in /etc/yum.repos.d

[epel]
name = epel
enabled = 1
baseurl = https://repo.citrite.net/ctx-remote-yum-fedora/epel/7/x86_64/
exclude = ocaml*
gpgcheck = 0

[base]
name = base
enabled = 1
baseurl = https://repo.citrite.net/centos/7.2.1511/os/x86_64/
exclude = ocaml*
gpgcheck = 0

[updates]
name = updates
enabled = 1
baseurl = https://repo.citrite.net/centos/7.2.1511/os/x86_64/
exclude = ocaml*
gpgcheck = 0

[extras]
name = extras
enabled = 1
baseurl = https://repo.citrite.net/centos/7.2.1511/os/x86_64/
exclude = ocaml*
gpgcheck = 0

