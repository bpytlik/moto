import urlparse

def bucket_name_from_url(url):
    print "using right bucket_name_from_url"
    pth = urlparse.urlparse(url).path
    print "pth:" + str(pth)

    l = pth.split("/")
    print "l:" + str(l)
    print "len was: " + str(len(l))
    if len(l) < 2:
        return None
    print "returning: " + l[1]
    return l[1]
    
    # if domain.startswith('www.'):
    #     domain = domain[4:]

    # if 'amazonaws.com' in domain:
    #     bucket_result = bucket_name_regex.search(domain)
    #     if bucket_result:
    #         return bucket_result.groups()[0]
    # else:
    #     if '.' in domain:
    #         return domain.split(".")[0]
    #     else:
    #         # No subdomain found.
    #         return None
