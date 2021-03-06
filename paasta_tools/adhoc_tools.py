# Copyright 2015-2016 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import absolute_import
from __future__ import unicode_literals

import logging

import service_configuration_lib

from paasta_tools.long_running_service_tools import LongRunningServiceConfig
from paasta_tools.utils import deep_merge_dictionaries
from paasta_tools.utils import DEFAULT_SOA_DIR
from paasta_tools.utils import get_paasta_branch
from paasta_tools.utils import load_v2_deployments_json
from paasta_tools.utils import NoConfigurationForServiceError
from paasta_tools.utils import NoDeploymentsAvailable
from paasta_tools.utils import prompt_pick_one


log = logging.getLogger(__name__)


def load_adhoc_job_config(service, instance, cluster, load_deployments=True, soa_dir=DEFAULT_SOA_DIR):
    general_config = service_configuration_lib.read_service_configuration(
        service,
        soa_dir=soa_dir
    )
    adhoc_conf_file = "adhoc-%s" % cluster
    log.info("Reading adhoc configuration file: %s.yaml", adhoc_conf_file)
    instance_configs = service_configuration_lib.read_extra_service_information(
        service_name=service,
        extra_info=adhoc_conf_file,
        soa_dir=soa_dir
    )

    if instance not in instance_configs:
        raise NoConfigurationForServiceError(
            "%s not found in config file %s/%s/%s.yaml." % (instance, soa_dir, service, adhoc_conf_file)
        )

    general_config = deep_merge_dictionaries(overrides=instance_configs[instance], defaults=general_config)

    branch_dict = {}
    if load_deployments:
        deployments_json = load_v2_deployments_json(service, soa_dir=soa_dir)
        branch = general_config.get('branch', get_paasta_branch(cluster, instance))
        deploy_group = general_config.get('deploy_group', branch)
        branch_dict = deployments_json.get_branch_dict_v2(service, branch, deploy_group)

    return AdhocJobConfig(
        service=service,
        cluster=cluster,
        instance=instance,
        config_dict=general_config,
        branch_dict=branch_dict,
    )


class AdhocJobConfig(LongRunningServiceConfig):

    def __init__(self, service, instance, cluster, config_dict, branch_dict):
        super(AdhocJobConfig, self).__init__(
            cluster=cluster,
            instance=instance,
            service=service,
            config_dict=config_dict,
            branch_dict=branch_dict,
        )


def get_default_interactive_config(service, cluster, soa_dir, load_deployments=False):
    default_job_config = {
        'cpus': 4,
        'mem': 10240,
        'disk': 1024
    }

    try:
        job_config = load_adhoc_job_config(service=service, instance='interactive', cluster=cluster, soa_dir=soa_dir)
    except NoConfigurationForServiceError:
        job_config = AdhocJobConfig(
            service=service,
            instance='interactive',
            cluster=cluster,
            config_dict={},
            branch_dict={},
        )
    except NoDeploymentsAvailable:
        job_config = load_adhoc_job_config(
            service=service, instance='interactive', cluster=cluster, soa_dir=soa_dir, load_deployments=False)

    if not job_config.branch_dict and load_deployments:
        deployments_json = load_v2_deployments_json(service, soa_dir=soa_dir)
        deploy_group = prompt_pick_one(
            (
                deployment.encode('utf-8')
                for deployment in deployments_json['deployments'].keys()
            ),
            choosing='deploy group',
        )
        job_config.config_dict['deploy_group'] = deploy_group
        job_config.branch_dict['docker_image'] = deployments_json.get_docker_image_for_deploy_group(deploy_group)

    for key, value in default_job_config.items():
        job_config.config_dict.setdefault(key, value)

    return job_config
