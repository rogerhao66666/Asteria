from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from typing import Any
class Kind(str,Enum):
 COMMAND="command";SEQUENCE="sequence";PARALLEL="parallel";WAIT="wait";WAIT_EVENT="wait_event";BRANCH="branch";LOOP="loop";EMIT_EVENT="emit_event";SET_VARIABLE="set_variable";NESTED="nested"
@dataclass(frozen=True,slots=True)
class Expression:
 op:str;args:tuple[Any,...]=()
 def eval(self,c):
  def v(x):
   if isinstance(x,Expression):return x.eval(c)
   if isinstance(x,str) and x.startswith("$"):return c.resolve(x[1:])
   return x
  a=[v(x) for x in self.args]
  return {"value":lambda:a[0] if a else None,"eq":lambda:a[0]==a[1],"ne":lambda:a[0]!=a[1],"gt":lambda:a[0]>a[1],"gte":lambda:a[0]>=a[1],"lt":lambda:a[0]<a[1],"lte":lambda:a[0]<=a[1],"and":lambda:all(a),"or":lambda:any(a),"not":lambda:not a[0]}[self.op]()
@dataclass(slots=True)
class Context:
 parameters:dict[str,Any]=field(default_factory=dict);variables:dict[str,Any]=field(default_factory=dict);event:dict[str,Any]=field(default_factory=dict)
 def resolve(self,path):
  root,*parts=path.split(".");cur={"param":self.parameters,"var":self.variables,"event":self.event}.get(root)
  for p in parts:
   if not isinstance(cur,dict):return None
   cur=cur.get(p)
  return cur
def bind(v,c):
 if isinstance(v,str) and v.startswith("$"):return c.resolve(v[1:])
 if isinstance(v,dict):return {k:bind(x,c) for k,x in v.items()}
 if isinstance(v,list):return [bind(x,c) for x in v]
 if isinstance(v,tuple):return tuple(bind(x,c) for x in v)
 return v
@dataclass(frozen=True,slots=True)
class Command:
 channel:str;action:str;args:dict[str,Any]=field(default_factory=dict);blocking:bool=False
@dataclass(frozen=True,slots=True)
class Node:
 id:str;kind:Kind;children:tuple["Node",...]=();else_children:tuple["Node",...]=();command:Command|None=None;duration_ms:float=0;event_name:str|None=None;condition:Expression|None=None;loop_count:int=0;variable:str|None=None;value:Any=None;sequence_ref:str|None=None
@dataclass(slots=True)
class Sequence:
 id:str;root:Node;parameters:tuple[str,...]=();metadata:dict[str,Any]=field(default_factory=dict)
 def validate(self):
  seen=set()
  def w(n):
   if not n.id or n.id in seen:raise ValueError("duplicate/empty node id")
   seen.add(n.id)
   if n.kind==Kind.COMMAND and n.command is None:raise ValueError("command required")
   if n.kind==Kind.WAIT and n.duration_ms<0:raise ValueError("negative wait")
   if n.kind in (Kind.WAIT_EVENT,Kind.EMIT_EVENT) and not n.event_name:raise ValueError("event required")
   if n.kind==Kind.BRANCH and n.condition is None:raise ValueError("condition required")
   if n.kind==Kind.LOOP and n.loop_count<0:raise ValueError("negative loop")
   if n.kind==Kind.NESTED and not n.sequence_ref:raise ValueError("sequence_ref required")
   for x in n.children+n.else_children:w(x)
  w(self.root)
class Library:
 def __init__(self):self.items={}
 def add(self,s):s.validate();self.items[s.id]=s
 def get(self,i):return self.items[i]
