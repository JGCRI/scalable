Getting Started with Scalable
=============================

Getting started with Scalable is easy. The first step is to install Scalable.


Installation
------------

Use the package manager `pip <https://pip.pypa.io/en/stable/>`_ to install 
scalable.

.. code-block:: bash

    [user@localhost ~]$ pip install scalable


Alternatively, the git repo can be cloned directly and installed locally. The 
git repo should be cloned to the preferred working directory. 

.. code-block:: bash

    [user@localhost <local_work_dir>]$ git clone https://github.com/JGCRI/scalable.git
    [user@localhost <local_work_dir>]$ pip install ./scalable


Compatibility Requirements
--------------------------

`Docker <https://www.docker.com/>`_ is needed to run the bootstrap script. The 
script itself is preferred to be ran in a linux environment. For Windows users, 
`Git Bash <https://git-scm.com/>`_ is recommended for bootstrapping. For MacOS 
users, just the terminal app should suffice.

HPC Schedulers Supported: Slurm

Tools required on HPC Host: apptainer

Tools required on Local Host: docker


Work Directory Setup
--------------------

A work directory needs to be setup on the remote HPC host which would ensure the 
presence and a structured location for all required dependencies and any 
outputs. The provided bootstrap script helps in setting up the work directory 
and the containers which would be used as workers. **It is highly recommended 
to use the bootstrap script to use scalable.** Moreover, since the bootstrap 
scripts attempts to connect to the HPC host multiple times, **it is also highly 
recommended to have password-less ssh login enabled through private keys.** 
Otherwise, a password would need to be entered up to 15 times when running the 
script only once. A guide to setup key based authentication could be found 
`on this website 
<https://www.digitalocean.com/community/tutorials/how-to-configure-ssh-key-based-authentication-on-a-linux-server>`_.

Once scalable is installed through pip, navigate to a directory on your local 
computer where the bootstrap script can place containers, logs, and any other 
required dependency. The bootstrap script downloads and builds files both on 
your local system and the HPC system. 

.. code-block:: bash

    [user@localhost ~]$ cd <local_work_dir>
    [user@localhost <local_work_dir>]$ scalable_bootstrap

Follow and answer the prompts in the bootstrap script. All the dependencies will 
be automatically downloaded. Once everything has been downloaded and built, the 
script will initiate a SSH Session with the HPC Host logging in the user to the 
work directory on the HPC. 

The python3 command is aliased to start a server too. Simply calling python3 
will launch an interactive session with all the dependencies. A file or other 
arguments can also be given to python3 and they will be ran as a python file 
within a container. **Only files present in the current work directory and 
subdirectories on the HPC Host can be ran this way.** Any files stored above the 
current work directory would need to be copied under it to be ran. 

.. code-block:: bash

    [user@hpchost <work_dir>]$ python3
    [user@hpchost <work_dir>]$ python3 <filename>.py

If the script fails in the middle, or if a new session needs to be started, 
simply run the same command again and the bootstrap script will pickup where it 
left off. If everything is already installed then the script will log in to the 
HPC SSH session directly. For everything to function properly, it is 
recommended to use the bootstrap script every time scalable needs to be used. 
The initial setup takes time but the script connects to the HPC Host directly 
only checking for required dependencies if everything is already installed. 

Next Steps
----------

Once the work directory is setup, python scripts can be ran according to what 
is listed in the :ref:`api_section` section of the :doc:`index` page. The 
:ref:`demos_section` section provides simple demos of some workflows that can be 
ran using scalable. The :ref:`how_tos_section` section provides some guidance on 
how to use some of the features of scalable. Please also feel free to open an 
issue `here <https://github.com/JGCRI/scalable/issues>`_ if any issues are 
encountered or if any help is needed.

