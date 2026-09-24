"""Small HTML reader for public career pages; never executes page scripts."""
from html.parser import HTMLParser
from .normalization import plain

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def find(self, predicate):
        result=[]
        for child in self.children:
            if isinstance(child,Node):
                if predicate(child):result.append(child)
                result.extend(child.find(predicate))
        return result
    def text(self):
        return ' '.join(c.text() if isinstance(c,Node) else c for c in self.children).strip()
    def has_class(self,name):return name in self.attrs.get('class','').split()

class Tree(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(html)
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs);self.stack[-1].children.append(node)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(node)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                del self.stack[i:];break
    def handle_data(self,data):
        if self.stack[-1].tag not in ('script','style'):self.stack[-1].children.append(data)
