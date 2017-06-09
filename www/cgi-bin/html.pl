#!/usr/bin/env perl
my $title = 'My Page';
my $page = <<END;
<html>
    <head><title>$title</title></head>
    <body>This is a page.</body>
</html>
END
my $page_length = length $page;
print "content-type: text/html\r\n";
print "content-length: $page_length\r\n\r\n";
print $page
