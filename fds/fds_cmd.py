#!/usr/bin/env python
import json
import logging
import os
from os.path import expanduser
import argcomplete
import argparse
import sys
from argcomplete.completers import ChoicesCompleter
from fds import FDSClientConfiguration, GalaxyFDSClient
from fds.model.fds_object_metadata import FDSObjectMetadata
from fds.model.upload_part_result_list import UploadPartResultList

logger = None
access_key = None
secret_key = None
region = ''
fds_config = None
enable_https = True
enable_cdn = False
end_point = None
fds_client = None


def print_config(name, value):
    global logger
    if not (logger is None):
        logger.debug('Config param [' + str(name) + '] ' + ' value [' + str(value) + ']')


def read_local_config():
    global logger
    config_dir = os.path.join(expanduser("~"), ".config", "fds", "client.config");
    if not os.path.exists(config_dir):
        if not (logger is None):
            logger.debug("local config not exist [" + str(config_dir) + "]")
            return {}
    with open(config_dir) as f:
        return json.load(fp=f)


def parse_argument(args):
    global method, bucket_name, region, object_name, \
        enable_cdn, enable_https, list_dir, list_objects, \
        data_file, start_mark, metadata, length, offset, \
        access_key, secret_key, end_point
    local_config = read_local_config()
    method = args.method
    print_config('method', method)
    if args.bucket:
        bucket_name = args.bucket
    else:
        bucket_name = local_config.get('bucket')
    print_config('bucket name', bucket_name)
    region = local_config.get('region')
    if args.region:
        region = args.region
        if args.end_point:
            end_point = args.end_point
    else:
        if args.end_point:
            end_point = args.end_point
        else:
            end_point = local_config.get('end_point')

    print_config('region name', bucket_name)
    object_name = args.object
    print_config('object name', object_name)
    enable_cdn = args.CDN
    print_config('cdn enabled', enable_cdn)
    enable_https = args.https
    print_config('https enabled', enable_https)
    list_dir = args.list_dir
    print_config('list dir', list_dir)
    list_objects = args.list_objects
    print_config('list objects', list_objects)
    data_file = args.data_file
    print_config('data file', data_file)
    start_mark = args.start_mark
    print_config('start mark', start_mark)
    metadata = args.metadata
    print_config('meta data', metadata)
    length = args.length
    print_config('length', length)
    offset = args.offset
    print_config('offset', offset)
    end_point = args.end_point
    print_config('end point', end_point)
    if args.ak:
        access_key = args.ak
    else:
        access_key = local_config.get('ak')
    print_config('access key', access_key)
    if args.sk:
        secret_key = args.sk
    else:
        secret_key = local_config.get('sk')


def get_buckets(fds_client):
    buckets = fds_client.list_buckets()
    return buckets


def list_buckets(fds_client, prefix, start_mark):
    buckets = get_buckets(fds_client)
    for i in buckets:
        if i.bucket_name.startswith(prefix) and i.bucket_name >= start_mark:
            sys.stdout.write(i.bucket_name + '/')
            sys.stdout.write('\n')


def bucket_name_completer(prefix, parsed_args, **kwargs):
    parse_argument(args=parsed_args)

    if not (access_key is None) and not (secret_key is None) and not (region is None):
        argcomplete.warn(str(enable_https) + ' ' + str(enable_cdn) + ' ' + str(region))
        fds_config = FDSClientConfiguration(region_name=region,
                                            enable_https=enable_https,
                                            enable_cdn_for_download=enable_cdn,
                                            enable_cdn_for_upload=enable_cdn)
        fds_client = GalaxyFDSClient(access_key=access_key,
                                     access_secret=secret_key,
                                     config=fds_config)
        bucket_list = get_buckets(fds_client=fds_client)
        rtn = []
        for i in bucket_list:
            if i.startswith(prefix):
                rtn.append(i)
        return rtn
    return ['a', 'b', 'c']


def check_region(region):
    pass


def check_bucket_name(bucket_name):
    pass


def check_object_name(object_name):
    pass


def check_metadata(metadata):
    pass


def put_object(data_file, bucket_name, object_name, metadata):
    check_bucket_name(bucket_name)
    check_object_name(object_name)
    check_metadata(metadata)
    fds_metadata = parse_metadata_from_str(metadata)
    if data_file:
        fd = open(data_file, 'r')
        fds_client.put_object(bucket_name=bucket_name,
                              object_name=object_name,
                              data=fd,
                              metadata=fds_metadata)
    else:
        logger.debug('Put object with multipart upload')
        upload_token = fds_client.init_multipart_upload(bucket_name=bucket_name,
                                                        object_name=object_name)
        logger.debug('Upload id [' + upload_token.upload_id + ']')
        byte_buffer = bytearray(10 * 1024 * 1024)
        part_number = 0
        upload_list = []
        while True:
            length = sys.stdin.readinto(byte_buffer)
            if length <= 0:
                break
            print(length)

            rtn = fds_client.upload_part(bucket_name=upload_token.bucket_name,
                                         object_name=upload_token.object_name,
                                         upload_id=upload_token.upload_id,
                                         part_number=part_number,
                                         data=byte_buffer[0:length])
            upload_list.append(rtn)
            part_number += 1

        upload_part_result = UploadPartResultList({"uploadPartResultList": upload_list})
        print(json.dumps(upload_part_result))
        fds_client.complete_multipart_upload(bucket_name=upload_token.bucket_name,
                                             object_name=upload_token.object_name,
                                             upload_id=upload_token.upload_id,
                                             metadata=fds_metadata,
                                             upload_part_result_list=json.dumps(upload_part_result))


def parse_metadata_from_str(metadata):
    fds_metadata = None
    if metadata:
        fds_metadata = FDSObjectMetadata()
        for i in metadata.split(';'):
            key, value = i.split(':', 1)
            if key and value:
                if key.startswith(FDSObjectMetadata.USER_DEFINED_METADATA_PREFIX):
                    fds_metadata.add_user_metadata(key, value)
                else:
                    fds_metadata.add_header(key, value)
    return fds_metadata


def get_object(data_file, bucket_name, object_name, metadata, offset, length):
    check_bucket_name(bucket_name)
    check_object_name(object_name)
    fds_object = fds_client.get_object(bucket_name=bucket_name,
                                       object_name=object_name,
                                       position=offset)
    length_left = length
    if length_left == -1:
        length_left = sys.maxsize
    try:
        if data_file:
            with open(data_file, "w") as f:
                for chunk in fds_object.stream:
                    l = min(length_left, len(chunk));
                    f.write(chunk[0:l])
                    length_left -= l
                    if length_left <= 0:
                        break
        else:
            for chunk in fds_object.stream:
                l = min(length_left, len(chunk))
                sys.stdout.write(chunk[0:l])
                length_left -= l
                if length_left <= 0:
                    break
    finally:
        fds_object.stream.close()


def post_object(data_file, bucket_name, metadata):
    with open(data_file, 'r') as f:
        fds_object = fds_client.post_object(bucket_name=bucket_name, data=f, metadata=metadata)
        logger.debug('Post object [' + fds_object.object_name + ']')
        sys.stdout.write(fds_object.object_name)


def put_bucket(bucket_name):
    check_bucket_name(bucket_name=bucket_name)
    fds_client.create_bucket(bucket_name)


def get_bucket_acl(bucket_name):
    acl = fds_client.get_bucket_acl(bucket_name=bucket_name)
    sys.stdout.write('ACL:\n')
    sys.stdout.write('gratee_id\tgrant_type\tpermission\n')
    for i in acl.get_grant_list():
        sys.stdout.write(str(i.grantee['id']) + '\t' + str(i.type) + '\t' + str(i.permission.to_string()) + '\n')


def delete_object(bucket_name, object_name):
    check_bucket_name(bucket_name=bucket_name)
    check_object_name(object_name=object_name)
    fds_client.delete_object(bucket_name=bucket_name,
                             object_name=object_name)


def delete_bucket(bucket_name):
    fds_client.delete_bucket(bucket_name=bucket_name)


def head_object(bucket_name, object_name):
    return fds_client.does_object_exists(bucket_name=bucket_name,
                                         object_name=object_name)


def head_bucket(bucket_name):
    return fds_client.does_bucket_exist(bucket_name=bucket_name)


def list_directory(bucket_name, object_name_prefix, start_mark):
    if not object_name_prefix:
        object_name_prefix = ''
    path_prefix = object_name_prefix
    if len(path_prefix) > 0 and not path_prefix.endswith('/'):
        path_prefix = path_prefix + '/'
    list_result = fds_client.list_objects(bucket_name=bucket_name,
                                          prefix=path_prefix,
                                          delimiter='/',
                                          )
    if start_mark:
        logger.info('start_marker: ' + start_mark)
        list_result.next_marker = bucket_name + '/' + path_prefix + start_mark
        list_result.is_truncated = True
        list_result = fds_client.list_next_batch_of_objects(list_result)

    prefix_len = len(path_prefix)

    while True:
        for i in list_result.common_prefixes:
            sys.stdout.write(i[prefix_len:])
            sys.stdout.write('\n')
        for i in list_result.objects:
            sys.stdout.write(i.object_name[prefix_len:])
            sys.stdout.write('\n')
        sys.stdout.flush()
        if not list_result.is_truncated:
            break
        list_result = fds_client.list_next_batch_of_objects(list_result)


def list_object(bucket_name, object_name_prefix, start_mark=''):
    list_result = fds_client.list_objects(bucket_name=bucket_name,
                                          prefix=object_name_prefix,
                                          delimiter='')
    if start_mark:
        list_result.is_truncated = True
        list_result.next_marker = bucket_name + '/' + object_name_prefix + start_mark
        list_result = fds_client.list_next_batch_of_objects(list_result)

    for i in list_result.common_prefixes:
        sys.stdout.write(i)
        sys.stdout.write('\n')
    for i in list_result.objects:
        sys.stdout.write(i.object_name)
        sys.stdout.write('\n')
    sys.stdout.flush()
    if list_result.is_truncated:
        sys.stdout.write('...\n')


def main():
    parser = argparse.ArgumentParser(description="FDS command-line tool",
                                     epilog="Doc - http://docs.api.xiaomi.com/fds/")

    parser.add_argument('-m', '--method',
                        nargs='?',
                        metavar='method',
                        const='put',
                        type=str,
                        dest='method',
                        help='Method of the request. Can be one of put/get/delete/post/head (default: put)'
                        ).completer = ChoicesCompleter(('put', 'get', 'delete', 'post', 'head'))

    parser.add_argument('-b', '--bucket',
                        nargs='?',
                        metavar='bucket',
                        type=str,
                        dest='bucket',
                        help='Name of bucket to operate'
                        ).completer = bucket_name_completer

    parser.add_argument('-o', '--object',
                        nargs='?',
                        metavar='object',
                        type=str,
                        dest='object',
                        help='Name of object to operate'
                        )

    parser.add_argument('-r', '--region',
                        nargs='?',
                        metavar='region',
                        type=str,
                        dest='region',
                        help='Can be one of cnbj0/cnbj1/cnbj2/awsbj0/awsusor0/awssgp0/awsde0 (default: cnbj0)'
                        )

    parser.add_argument('-e', '--end_point',
                        nargs='?',
                        metavar='end point',
                        type=str,
                        dest='end_point',
                        help='can be [cnbj1.fds.api.xiaomi.com] or empty'
                        )

    parser.add_argument('-c', '--CDN',
                        metavar='CDN',
                        action='store_const',
                        const=False,
                        dest='CDN',
                        default=False,
                        help='If toggled, CDN is enabled'
                        )

    parser.add_argument('--https',
                        metavar='https',
                        nargs='?',
                        dest='https',
                        default=True,
                        help='If toggled, https is enabled'
                        )

    parser.add_argument('--ak',
                        nargs='?',
                        metavar='ACCESS_KEY',
                        dest='ak',
                        help='Specify access key'
                        )

    parser.add_argument('--sk',
                        nargs='?',
                        metavar='SECRET_KEY',
                        dest='sk',
                        help='Specify secret key'
                        )

    parser.add_argument('-L', '--list',
                        nargs='?',
                        metavar='list directory',
                        const='',
                        type=str,
                        dest='list_dir',
                        help='List Bucket/Object under current user')

    parser.add_argument('-l', '--list_objects',
                        nargs='?',
                        metavar='list objects',
                        const='',
                        type=str,
                        dest='list_objects',
                        help='List Bucket/Object under current user')

    parser.add_argument('-d', '--data',
                        nargs='?',
                        metavar='data file',
                        dest='data_file',
                        help='file to be uploaded or stored')

    parser.add_argument('--offset',
                        nargs='?',
                        metavar='offset',
                        type=int,
                        const=0,
                        default=0,
                        dest='offset',
                        help='offset of object to be read')

    parser.add_argument('--length',
                        nargs='?',
                        metavar='length',
                        type=int,
                        dest='length',
                        const=-1,
                        default=-1,
                        help='length of object to be read')

    parser.add_argument('--metadata',
                        nargs='?',
                        metavar='meta data of object to be uploaded',
                        dest='metadata',
                        help='example: "content-type:text/json;x-xiaomi-meta-user-defined:foo"')

    parser.add_argument('--start',
                        nargs='?',
                        metavar='start mark',
                        type=str,
                        dest='start_mark',
                        const=None,
                        default=None,
                        help='used with -l or -L option, returned object name should be *no less* than start mark in dictionary order'
                        )

    parser.add_argument('--debug',
                        metavar='debug',
                        action='store_const',
                        const=True,
                        default=False,
                        dest='debug',
                        help='If toggled, print debug log')

    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    # set logging
    log_format = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=log_format)
    global logger
    logger = logging.getLogger('fds.cmd')

    debug_enabled = args.debug

    if debug_enabled:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    ## read config
    parse_argument(args=args)


    check_region(region=region)
    check_bucket_name(bucket_name=bucket_name)
    global fds_config
    fds_config = FDSClientConfiguration(region_name=region,
                                        enable_https=enable_https,
                                        enable_cdn_for_download=enable_cdn,
                                        enable_cdn_for_upload=enable_cdn)
    global end_point
    if not end_point is None:
        fds_config.set_endpoint(end_point)
    global fds_client
    fds_client = GalaxyFDSClient(access_key=access_key,
                                 access_secret=secret_key,
                                 config=fds_config)

    try:
        if not (list_dir is None):
            if not (bucket_name is None):
                list_directory(bucket_name=bucket_name,
                               object_name_prefix=list_dir, start_mark=start_mark)
            else:
                list_buckets(fds_client=fds_client, prefix=list_dir, start_mark=start_mark)
        elif not (list_objects is None):
            if not (bucket_name is None):
                list_object(bucket_name=bucket_name, object_name_prefix=list_objects, start_mark=start_mark)
            else:
                list_buckets(fds_client=fds_client, prefix=list_objects, start_mark=start_mark)
            pass
        else:
            if method == 'put':
                if object_name:
                    put_object(data_file=data_file,
                               bucket_name=bucket_name,
                               object_name=object_name,
                               metadata=metadata)
                else:
                    put_bucket(bucket_name)
                pass
            elif method == 'get':
                if object_name:
                    get_object(data_file=data_file,
                               bucket_name=bucket_name,
                               object_name=object_name,
                               metadata=metadata,
                               offset=offset,
                               length=length)
                else:
                    get_bucket_acl(bucket_name=bucket_name)
                pass
            elif method == 'post':
                post_object(data_file=data_file,
                            bucket_name=bucket_name,
                            metadata=metadata)
                pass
            elif method == 'delete':
                if object_name:
                    delete_object(bucket_name=bucket_name,
                                  object_name=object_name)
                else:
                    delete_bucket(bucket_name=bucket_name)
                pass
            elif method == 'head':
                if object_name:
                    if not head_object(bucket_name=bucket_name,
                                       object_name=object_name):
                        exit(1)
                else:
                    if not head_bucket(bucket_name=bucket_name):
                        exit(1)
            else:
                parser.print_help()
                print("Config:")
                print("put following json into ~/.config/fds/client.config")
                print("{")
                print("  \"ak\":\"ACCESS_KEY\",")
                print("  \"sk\":\"SECRET_KEY\",")
                print("  \"region\":\"REGION\",")
                print("  \"end_point\":\"END_POINT\" (optional)")
                print("}")
                print("Usage Example:")
                print("\t[create bucket]\n\t\tfds -m put -b BUCKET_NAME")
                print("\t[list buckets]\n\t\tfds -l")
                print("\t[list objects under bucket]\n\t\tfds -l -b BUCKET_NAME")
                print("\t[list directory under bucket]\n\t\tfds -L DIR -b BUCKET_NAME")
                print("\t[create object under bucket]\n\t\tfds -m put -b BUCKET_NAME -o OBJECT_NAME -d FILE_PATH")
                print("\t[create object with pipline]\n\t\tcat file | fds -m put -b BUCKET_NAME -o OBJECT_NAME")

    except Exception as e:
        sys.stderr.write(e.message)
        sys.stderr.flush()
        if debug_enabled:
            logger.debug(e, exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
