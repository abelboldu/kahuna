#!/usr/bin/env jython

from __future__ import with_statement  # jython 2.5.2 issue
import logging
import os
from java.io import File
from kahuna.abstract import AbsPlugin
from kahuna.config import ConfigLoader
from kahuna.utils.prettyprint import pprint_templates
from com.google.common.collect import Iterables
from optparse import OptionParser
from org.jclouds.abiquo.domain.exception import AbiquoException
from org.jclouds.compute import RunNodesException
from org.jclouds.domain import LoginCredentials
from org.jclouds.io import Payloads
from org.jclouds.rest import AuthorizationException
from org.jclouds.util import Strings2

log = logging.getLogger('kahuna')


class MothershipPlugin(AbsPlugin):
    """ Mothership plugin """
    def __init__(self):
        self.__config = ConfigLoader().load("mothership.conf",
                "config/mothership.conf")
        self.__scriptdir = "kahuna/plugins/mothership"

    # Override the endpoint address and credentials to create the
    # context
    def _config_overrides(self):
        overrides = {}
        overrides['address'] = self.__config.get("mothership", "host")
        overrides['user'] = self.__config.get("mothership", "user")
        overrides['password'] = self.__config.get("mothership", "password")
        return overrides

    # Override the commands factory method because the command names we want
    # can not be used as valid python class method names
    def _commands(self):
        """ Returns the provided commands, mapped to handler methods """
        commands = {}
        commands['deploy-abiquo'] = self.deploy_abiquo
        commands['deploy-chef'] = self.deploy_chef
        commands['deploy-kvm'] = self.deploy_kvm
        commands['deploy-vbox'] = self.deploy_vbox
        commands['list-templates'] = self.list_templates
        return commands

    def list_templates(self, args):
        """ List all available templates """
        try:
            admin = self._context.getAdministrationService()
            user = admin.getCurrentUser()
            enterprise = user.getEnterprise()
            templates = enterprise.listTemplates()
            pprint_templates(templates)
        except (AbiquoException, AuthorizationException), ex:
            print "Error: %s" % ex.getMessage()

    def deploy_chef(self, args):
        """ Deploys and configures a Chef Server """
        compute = self._context.getComputeService()

        try:
            name = self.__config.get("deploy-chef", "template")
            log.info("Loading template...")
            options = self._template_options(compute, "deploy-chef")
            template = compute.templateBuilder() \
                    .imageNameMatches(name) \
                    .options(options.blockOnPort(4000, 90)) \
                    .build()

            log.info("Deploying %s..." % template.getImage().getName())
            node = Iterables.getOnlyElement(
                    compute.createNodesInGroup("kahuna-chef", 1, template))

            cookbooks = self.__config.get("deploy-chef", "cookbooks")
            with open(self.__scriptdir + "/configure-chef.sh", "r") as f:
                script = f.read() % {'cookbooks': cookbooks}

            log.info("Configuring node with cookbooks: %s..." % cookbooks)
            compute.runScriptOnNode(node.getId(), script)

            log.info("Chef Server configured!")
            log.info("You can access the admin console at: http://%s:4040"
                    % Iterables.getOnlyElement(node.getPrivateAddresses()))

            log.info("These are the certificates to access the API:")
            self._print_node_file(self._context, node,
                    "/etc/chef/validation.pem")
            self._print_node_file(self._context, node, "/etc/chef/webui.pem")

        except RunNodesException, ex:
            self._print_node_errors(ex)

    def deploy_kvm(self, args):
        """ Deploys and configures a KVM hypervisor """
        self._deploy_aim("deploy-kvm", "kahuna-kvm")

    def deploy_vbox(self, args):
        """ Deploys and configures a VirtualBox hypervisor """
        self._deploy_aim("deploy-vbox", "kahuna-vbox")

    def deploy_abiquo(self, args):
        """ Deploys and configures an Abiquo platform """
        parser = OptionParser(usage="mothership deploy-abiquo <options>")
        parser.add_option('-t', '--template-id',
                help='The id of the template to deploy',
                action='store', dest='template')
        parser.add_option('-p', '--properties',
                help='Path to the abiquo.properties file to use',
                action='store', dest='props')
        (options, args) = parser.parse_args(args)

        if not options.template or not options.props:
            parser.print_help()
            return

        compute = self._context.getComputeService()

        try:
            log.info("Loading template...")
            template_options = self._template_options(compute, "deploy-abiquo")
            template = compute.templateBuilder() \
                    .imageId(options.template) \
                    .options(template_options) \
                    .build()

            log.info("Deploying %s..." % template.getImage().getName())
            node = Iterables.getOnlyElement(
                    compute.createNodesInGroup("kahuna-abiquo", 1, template))

            self._upload_file_node(self._context, node, "/opt/abiquo/config",
                    options.props, True)

            log.info("Restarting Abiquo Tomcat...")
            compute.runScriptOnNode(node.getId(),
                    "service abiquo-tomcat restart")

            log.info("Abiquo configured at: %s" %
                    Iterables.getOnlyElement(node.getPrivateAddresses()))

        except RunNodesException, ex:
            self._print_node_errors(ex)

    # Utility functions
    def _deploy_aim(self, config_section, vapp_name):
        """ Deploys and configures an AIM based hypervisor """
        compute = self._context.getComputeService()

        try:
            name = self.__config.get(config_section, "template")
            log.info("Loading template...")
            options = self._template_options(compute, config_section)
            template = compute.templateBuilder() \
                    .imageNameMatches(name) \
                    .options(options) \
                    .build()

            log.info("Deploying %s..." % template.getImage().getName())
            node = Iterables.getOnlyElement(
                    compute.createNodesInGroup(vapp_name, 1, template))

            # Configuration values
            redishost = self.__config.get(config_section, "redis_host")
            redisport = self.__config.get(config_section, "redis_port")
            nfsto = self.__config.get(config_section, "nfs_to")
            nfsfrom = self.__config.get(config_section, "nfs_from")

            # abiquo-aim.ini
            self._complete_file("abiquo-aim.ini", {'redishost': redishost,
                'redisport': redisport, 'nfsto': nfsto})
            self._upload_file_node(self._context, node, "/etc/",
                    "abiquo-aim.ini")

            # configure-aim-node.sh
            with open(self.__scriptdir + "/configure-aim-node.sh", "r") as f:
                script = f.read() % {'nfsfrom': nfsfrom, 'nfsto': nfsto}

            log.info("Configuring node...")
            compute.runScriptOnNode(node.getId(), script)

            log.info("Node configured!")
            log.info("You can access it at: ssh://%s" %
                    Iterables.getOnlyElement(node.getPrivateAddresses()))

        except RunNodesException, ex:
            self._print_node_errors(ex)

    def _template_options(self, compute, deploycommand):
        login = LoginCredentials.builder() \
                .authenticateSudo(self.__config.getboolean(deploycommand,
                    "requires_sudo")) \
                .user(self.__config.get(deploycommand, "template_user")) \
                .password(self.__config.get(deploycommand, "template_pass")) \
                .build()
        return compute.templateOptions() \
                .overrideLoginCredentials(login) \
                .virtualDatacenter(self.__config.get("mothership", "vdc"))

    def _print_node_file(self, context, node, file):
        ssh = context.getUtils().sshForNode().apply(node)
        try:
            ssh.connect()
            payload = ssh.get(file)
            log.info(file)
            log.info(Strings2.toStringAndClose(payload.getInput()))
        finally:
            if payload:
                payload.release()
            if ssh:
                ssh.disconnect()

    def _upload_file_node(self, context, node, destination, filename,
            abs_path=False):
        ssh = context.getUtils().sshForNode().apply(node)
        path = filename if abs_path else self.__scriptdir + "/" + filename
        tmpfile = os.path.exists(path + ".tmp")
        file = File(path + ".tmp" if tmpfile else path)

        if abs_path:
            filename = os.path.basename(path)

        try:
            ssh.connect()
            log.info("Uploading file %s..." % filename)
            ssh.put(destination + "/" + filename,
                    Payloads.newFilePayload(file))
        finally:
            if ssh:
                ssh.disconnect()
            if tmpfile:
                os.remove(file.getPath())

    def _complete_file(self, filename, dictionary):
        with open(self.__scriptdir + "/" + filename, "r") as f:
            content = f.read()
        content = content % dictionary
        with open(self.__scriptdir + "/" + filename + ".tmp", "w") as f:
            f.write(content)
        log.info("File %s completed" % filename)

    def _print_node_errors(self, ex):
        for error in ex.getExecutionErrors().values():
            print "Error %s" % error.getMessage()
        for error in ex.getNodeErrors().values():
            print "Error %s" % error.getMessage()


def load():
    """ Loads the current plugin """
    return MothershipPlugin()
