from .responses import bucket_response, key_response

url_bases = [
    "https?://s3.amazonaws.com"
]

def bucket_response2(*args):
    return bucket_response(*args)

url_paths = {
    '{0}/(?P<bucket_name>[a-zA-Z0-9\-_.]+)': bucket_response,
    '{0}/(?P<bucket_name>[a-zA-Z0-9\-_.]+)/': bucket_response2,
    '{0}/(?P<bucket_name>[a-zA-Z0-9\-_.]+)/(?P<key_name>[a-zA-Z0-9\-_.]+)': \
        key_response
}
