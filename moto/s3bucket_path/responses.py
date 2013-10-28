from urlparse import parse_qs, urlparse
import re

from jinja2 import Template

from .models import s3bucket_path_backend
s3_backend = s3bucket_path_backend
from .utils import bucket_name_from_url

from moto.s3.responses import S3_ALL_BUCKETS, S3_BUCKET_GET_RESPONSE, \
     S3_BUCKET_CREATE_RESPONSE, S3_DELETE_BUCKET_SUCCESS, \
     S3_DELETE_NON_EXISTING_BUCKET, S3_DELETE_BUCKET_WITH_ITEMS_ERROR, \
     S3_DELETE_OBJECT_SUCCESS, S3_OBJECT_RESPONSE, S3_OBJECT_COPY_RESPONSE

def all_buckets():
    # No bucket specified. Listing all buckets
    all_buckets = s3_backend.get_all_buckets()
    template = Template(S3_ALL_BUCKETS)
    return template.render(buckets=all_buckets)


def bucket_response(request, full_url, headers):
    response = _bucket_response(request, full_url, headers)
    if isinstance(response, basestring):
        return 200, headers, response

    else:
        status_code, headers, response_content = response
        return status_code, headers, response_content


def _bucket_response(request, full_url, headers):
    parsed_url = urlparse(full_url)
    querystring = parse_qs(parsed_url.query)
    method = request.method

    bucket_name = bucket_name_from_url(full_url)
    l = parsed_url.path.split("/")
    if len(l) > 2 and l[2] != "":
        raise RuntimeError("WHEE l:" + str(l))
    if not bucket_name:
        # If no bucket specified, list all buckets
        return all_buckets()

    if method == 'GET':
        bucket = s3_backend.get_bucket(bucket_name)
        if bucket:
            prefix = querystring.get('prefix', [None])[0]
            delimiter = querystring.get('delimiter', [None])[0]
            result_keys, result_folders = s3_backend.prefix_query(bucket, prefix, delimiter)
            template = Template(S3_BUCKET_GET_RESPONSE)
            return template.render(
                bucket=bucket,
                prefix=prefix,
                delimiter=delimiter,
                result_keys=result_keys,
                result_folders=result_folders
            )
        else:
            return 404, headers, ""
    elif method == 'PUT':
        new_bucket = s3_backend.create_bucket(bucket_name)
        template = Template(S3_BUCKET_CREATE_RESPONSE)
        return template.render(bucket=new_bucket)
    elif method == 'DELETE':
        removed_bucket = s3_backend.delete_bucket(bucket_name)
        if removed_bucket is None:
            # Non-existant bucket
            template = Template(S3_DELETE_NON_EXISTING_BUCKET)
            return 404, headers, template.render(bucket_name=bucket_name)
        elif removed_bucket:
            # Bucket exists
            template = Template(S3_DELETE_BUCKET_SUCCESS)
            return 204, headers, template.render(bucket=removed_bucket)
        else:
            # Tried to delete a bucket that still has keys
            template = Template(S3_DELETE_BUCKET_WITH_ITEMS_ERROR)
            return 409, headers, template.render(bucket=removed_bucket)
    elif method == 'POST':
        #POST to bucket-url should create file from form
        if hasattr(request, 'form'):
            #Not HTTPretty
            form = request.form
        else:
            #HTTPretty, build new form object
            form = {}
            for kv in request.body.split('&'):
                k, v = kv.split('=')
                form[k] = v

        key = form['key']
        f = form['file']

        new_key = s3_backend.set_key(bucket_name, key, f)

        #Metadata
        meta_regex = re.compile('^x-amz-meta-([a-zA-Z0-9\-_]+)$', flags=re.IGNORECASE)
        for form_id in form:
            result = meta_regex.match(form_id)
            if result:
                meta_key = result.group(0).lower()
                metadata = form[form_id]
                new_key.set_metadata(meta_key, metadata)
        return 200, headers, ""
    else:
        raise NotImplementedError("Method {0} has not been impelemented in the S3 backend yet".format(method))


def key_response(request, full_url, headers):
    response = _key_response(request, full_url, headers)
    if isinstance(response, basestring):
        return 200, headers, response
    else:
        status_code, headers, response_content = response
        return status_code, headers, response_content


def _key_response(request, full_url, headers):
    import sys
    parsed_url = urlparse(full_url)
    method = request.method

    # key_name = parsed_url.path.lstrip('/')
    key_name = "/".join(parsed_url.path.rstrip("/").split("/")[2:])

    bucket_name = bucket_name_from_url(full_url)

    if hasattr(request, 'body'):
        # Boto
        body = request.body
    else:
        # Flask server
        body = request.data

    if method == 'GET':
        key = s3_backend.get_key(bucket_name, key_name)
        if key:
            headers.update(key.metadata)
            return 200, headers, key.value
        else:
            return 404, headers, ""
    if method == 'PUT':
        if 'x-amz-copy-source' in request.headers:
            # Copy key
            src_bucket, src_key = request.headers.get("x-amz-copy-source").split("/",1)
            s3_backend.copy_key(src_bucket, src_key, bucket_name, key_name)
            template = Template(S3_OBJECT_COPY_RESPONSE)
            return template.render(key=src_key)
        streaming_request = hasattr(request, 'streaming') and request.streaming
        closing_connection = headers.get('connection') == 'close'
        if closing_connection and streaming_request:
            # Closing the connection of a streaming request. No more data
            new_key = s3_backend.get_key(bucket_name, key_name)
        elif streaming_request:
            # Streaming request, more data
            new_key = s3_backend.append_to_key(bucket_name, key_name, body)
        else:
            # Initial data
            new_key = s3_backend.set_key(bucket_name, key_name, body)
            request.streaming = True

            #Metadata
            meta_regex = re.compile('^x-amz-meta-([a-zA-Z0-9\-_]+)$', flags=re.IGNORECASE)
            for header in request.headers:
                if isinstance(header, basestring):
                    result = meta_regex.match(header)
                    if result:
                        meta_key = result.group(0).lower()
                        metadata = request.headers[header]
                        new_key.set_metadata(meta_key, metadata)
        template = Template(S3_OBJECT_RESPONSE)
        headers.update(new_key.response_dict)
        return 200, headers, template.render(key=new_key)
    elif method == 'HEAD':
        key = s3_backend.get_key(bucket_name, key_name)
        if key:
            headers.update(key.metadata)
            headers.update(key.response_dict)
            return 200, headers, ""
        else:
            return 404, headers, ""
    elif method == 'DELETE':
        removed_key = s3_backend.delete_key(bucket_name, key_name)
        template = Template(S3_DELETE_OBJECT_SUCCESS)
        return 204, headers, template.render(bucket=removed_key)
    else:
        raise NotImplementedError("Method {0} has not been impelemented in the S3 backend yet".format(method))
