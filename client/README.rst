Client
======

Client can run in normal user mode, you don't need to be root/system administrator.
You can start client typing:

python client.py

Commands
========

::

    SERVER  - /server <server> <nick> [<port>]
    NICK    - /nick <nick>
    MSG     - /msg <toNick,> :<msg> [:<msg>]
    JOIN    - /join <channel,> [:<topic>]
    PART    - /part <channel,>
    TOPIC   - /topic <channel,> [:<topic>]
    LIST    - /list [channel,]
    QUIT    - /quit
    KICK    - /kick <channel> <nick>
    KILL    - /kill <nick>

Examples
========

::

    > /server localhost client
    > /nick client2
    > /msg client2 :Hi!
    > /msg client2,client3 :Hi!
    > /msg client2,client3 :Hi 2! :Hi 3!
    > /join #chan1
    > /part #chan1
    > /list
