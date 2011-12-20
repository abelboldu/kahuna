Abiquo API Jython client
========================

This project groups  a collection of examples of the Abiquo Cloud
Platform API, using Jython as a wrapper to the [Official Java client](https://github.com/abiquo/jclouds-abiquo).


Prerequisites
-------------

To run the examples you will need to install *Maven*, *Java* and *Jython*.


Building
---------

The only required step to build the Jython client is to configure
the classpath properly with all necessary dependencies. This is only needed the
first time, and can be done by running the following command:

    mvn compile

This will generate a *lib* directory with all needed dependencies and a
*CLASSPATH* file containing the CLASSPATH variable needed to run the Jython
client.

Once the classpath has been generated, you can run the Jython code by invoking
the wrapper script as follows:

    sh wrapper.sh            # To run all examples
    sh wrapper.sh clean      # To cleanup all data generated by the examples
    

Configuration
-------------

You can customize the data being generated by editing the **src/constants.py** file.

If you want to understand the code, or adapt it to your needs, you may want to take
a look at the official Java client project page:

 * [jclouds-abiquo Source code](https://github.com/abiquo/jclouds-abiquo)
 * [jclouds-abiquo Documentation](https://github.com/abiquo/jclouds-abiquo/wiki)


Note on patches/pull requests
-----------------------------
 
 * Fork the project.
 * Create a topic branch for your feature or bug fix.
 * Develop in the just created feature/bug branch.
 * Add tests for it. This is important so I don't break it in a future version unintentionally.
 * Commit.
 * Send me a pull request.


Issue Tracking
--------------

If you find any issue, please submit it to the [Bug tracking system](https://github.com/nacx/abijy/issues) and we
will do our best to fix it.


License
-------

This sowftare is licensed under the MIT license. See LICENSE file for details.

