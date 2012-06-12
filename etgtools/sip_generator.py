#---------------------------------------------------------------------------
# Name:        etgtools/sip_generator.py
# Author:      Robin Dunn
#
# Created:     3-Nov-2010
# Copyright:   (c) 2011 by Total Control Software
# License:     wxWindows License
#---------------------------------------------------------------------------

"""
The generator class for creating SIP definition files from the data
objects produced by the ETG scripts.
"""

import sys, os, re
import etgtools.extractors as extractors
import etgtools.generators as generators
from etgtools.generators import nci, Utf8EncodingStream, textfile_open, wrapText


divider = '//' + '-'*75 + '\n'
phoenixRoot = os.path.abspath(os.path.split(__file__)[0]+'/..')

class SipGeneratorError(RuntimeError):
    pass



# This is a list of types that are used as return by value or by reference
# function return types that we need to ensure are actually using pointer
# types in their CppMethodDef or cppCode wrappers.
forcePtrTypes = [ 'wxString', 
                  ]

#---------------------------------------------------------------------------

class SipWrapperGenerator(generators.WrapperGeneratorBase):
        
    def generate(self, module, destFile=None):
        stream = Utf8EncodingStream()
        
        # generate SIP code from the module and its objects
        self.generateModule(module, stream)
        
        # Write the contents of the stream to the destination file
        if not destFile:
            destFile = os.path.join(phoenixRoot, 'sip/gen', module.name + '.sip')
        f = textfile_open(destFile, 'wt')
        f.write(stream.getvalue())
        f.close()
            
        
    #-----------------------------------------------------------------------
    def generateModule(self, module, stream):
        assert isinstance(module, extractors.ModuleDef)

        # write the file header
        stream.write(divider + """\
// This file is generated by wxPython's SIP generator.  Do not edit by hand.
// 
// Copyright: (c) 2011 by Total Control Software
// License:   wxWindows License
""")
        if module.name == module.module:
            stream.write("""
%%Module( name=%s.%s, 
         keyword_arguments="All",
         use_argument_names=True, 
         all_raise_py_exception=True,
         language="C++")
{
    %%AutoPyName(remove_leading="wx")
};

%%Copying
    Copyright: (c) 2011 by Total Control Software
    License:   wxWindows License
%%End

%%DefaultDocstringFormat(name="deindented")

""" % (module.package, module.name))

            if module.name.startswith('_'):
                doc = ''
                if module.docstring:
                    doc = '\n"""\n%s\n"""\n' % module.docstring 
                stream.write("""\
%%Extract(id=pycode%s, order=5)
# This file is generated by wxPython's SIP generator.  Do not edit by hand.
# 
# Copyright: (c) 2011 by Total Control Software
# License:   wxWindows License
%s
from .%s import *

%%End

""" % ( module.name, doc, module.name))
            
        else:
            stream.write("//\n// This file will be included by %s.sip\n//\n" % module.module)
        
        stream.write(divider)

        self.module_name = module.module
        # C++ code to be written to the module's header 
        if module.headerCode:
            stream.write("\n%ModuleHeaderCode\n")
            for c in module.headerCode:
                stream.write('%s\n' % c)
            stream.write("%End\n\n")
                
        # %Imports and %Includes
        if module.imports:
            for i in module.imports:
                stream.write("%%Import %s.sip\n" % i)
            stream.write("\n")
        if module.includes:
            for i in module.includes:
                stream.write("%%Include %s.sip\n" % i)
            stream.write("\n")
        
        # C++ code to be written out to the generated module
        if module.cppCode:
            stream.write("%ModuleCode\n")
            for c in module.cppCode:
                stream.write('%s\n' % c)
            stream.write("%End\n")

        stream.write('\n%s\n' % divider)
            
        # Now generate each of the items in the module
        self.generateModuleItems(module, stream)
                    
        # Add code for the module initialization sections.
        if module.preInitializerCode:
            stream.write('\n%s\n\n%%PreInitialisationCode\n' % divider)
            for i in module.preInitializerCode:
                stream.write('%s\n' % i)
            stream.write('%End\n')            
        if module.initializerCode:
            stream.write('\n%s\n\n%%InitialisationCode\n' % divider)
            for i in module.initializerCode:
                stream.write('%s\n' % i)
            stream.write('%End\n')            
        if module.postInitializerCode:
            stream.write('\n%s\n\n%%PostInitialisationCode\n' % divider)
            for i in module.postInitializerCode:
                stream.write('%s\n' % i)
            stream.write('%End\n')            
            
        stream.write('\n%s\n' % divider)
        
        
        
    def generateModuleItems(self, module, stream):
        methodMap = {
            extractors.ClassDef         : self.generateClass,
            extractors.DefineDef        : self.generateDefine,
            extractors.FunctionDef      : self.generateFunction,
            extractors.EnumDef          : self.generateEnum,
            extractors.GlobalVarDef     : self.generateGlobalVar,
            extractors.TypedefDef       : self.generateTypedef,
            extractors.WigCode          : self.generateWigCode,
            extractors.PyCodeDef        : self.generatePyCode,
            extractors.PyFunctionDef    : self.generatePyFunction,
            extractors.PyClassDef       : self.generatePyClass,
            extractors.CppMethodDef     : self.generateCppMethod,
            extractors.CppMethodDef_sip : self.generateCppMethod_sip,
            }
        
        for item in module:
            if item.ignored:
                continue
            function = methodMap[item.__class__]
            function(item, stream)
        
        
    #-----------------------------------------------------------------------
    def generateFunction(self, function, stream, _needDocstring=True):
        assert isinstance(function, extractors.FunctionDef)
        if not function.ignored:
            stream.write('%s %s(' % (function.type, function.name))
            if function.items:
                stream.write('\n')
                self.generateParameters(function.items, stream, ' '*4)
            stream.write(')%s;\n' % self.annotate(function))

            if  _needDocstring:
                self.generateDocstring(function, stream, '')
                # We only write a docstring for the first overload, otherwise
                # SIP appends them all together.
                _needDocstring = False

            if function.cppCode:
                code, codeType = function.cppCode
                if codeType == 'sip':
                    stream.write('%MethodCode\n')
                    stream.write(nci(code, 4))
                    stream.write('%End\n')
                elif codeType == 'function':
                    raise NotImplementedError() # TODO: See generateMethod for an example, refactor to share code...
        for f in function.overloads:
            self.generateFunction(f, stream, _needDocstring)
        stream.write('\n')            

        
    def generateParameters(self, parameters, stream, indent):
        def _lastParameter(idx):
            if idx == len(parameters)-1:
                return True
            for i in range(idx+1, len(parameters)):
                if not parameters[i].ignored:
                    return False
            return True
        
        for idx, param in enumerate(parameters):
            if param.ignored:
                continue
            stream.write(indent)
            stream.write('%s %s' % (param.type, param.name))
            stream.write(self.annotate(param))
            if param.default:
                stream.write(' = %s' % param.default)
            if not _lastParameter(idx):
                stream.write(',')
            stream.write('\n')
        
        
    #-----------------------------------------------------------------------
    def generateEnum(self, enum, stream, indent=''):
        assert isinstance(enum, extractors.EnumDef)
        if enum.ignored:
            return
        name = enum.name
        if name.startswith('@'):
            name = ''
        stream.write('%senum %s%s\n%s{\n' % (indent, name, self.annotate(enum), indent))
        values = []
        for v in enum.items:
            if v.ignored:
                continue
            values.append("%s    %s%s" % (indent, v.name, self.annotate(v)))
        stream.write(',\n'.join(values))
        stream.write('%s\n%s};\n\n' % (indent, indent))
        
        
    #-----------------------------------------------------------------------
    def generateGlobalVar(self, globalVar, stream):
        assert isinstance(globalVar, extractors.GlobalVarDef)
        if globalVar.ignored:
            return

        stream.write('%s %s' % (globalVar.type, globalVar.name))
        stream.write('%s;\n\n' % self.annotate(globalVar))
        

    #-----------------------------------------------------------------------
    def generateDefine(self, define, stream):
        assert isinstance(define, extractors.DefineDef)
        if define.ignored:
            return
        # We're assuming that the #define is an integer value, tell sip that it is
        #stream.write('enum { %s };\n' % define.name)
        stream.write('const int %s;\n' % define.name)
        
        
    #-----------------------------------------------------------------------
    def generateTypedef(self, typedef, stream):
        assert isinstance(typedef, extractors.TypedefDef)
        if typedef.ignored:
            return
        stream.write('typedef %s %s' % (typedef.type, typedef.name))
        stream.write('%s;\n\n' % self.annotate(typedef))
        
        
    #-----------------------------------------------------------------------
    def generateWigCode(self, wig, stream, indent=''):
        assert isinstance(wig, extractors.WigCode)
        stream.write(nci(wig.code, len(indent), False))
        stream.write('\n\n')
    
    
    #-----------------------------------------------------------------------
    def generatePyCode(self, pc, stream, indent=''):
        assert isinstance(pc, extractors.PyCodeDef)
        if hasattr(pc, 'klass') and isinstance(pc.klass, extractors.ClassDef) and pc.klass.generatingInClass:
            pc.klass.generateAfterClass.append(pc)
        else:
            if len(indent) == 0:
                stream.write('%%Extract(id=pycode%s' % self.module_name)
                if pc.order is not None:
                    stream.write(', order=%d' % pc.order)
                stream.write(')\n')

            stream.write(nci(pc.code, len(indent)))

            if len(indent) == 0:
                stream.write('\n%End\n\n')
    
    #-----------------------------------------------------------------------
    def generatePyProperty(self, prop, stream, indent=''):
        assert isinstance(prop, extractors.PyPropertyDef)
        if prop.ignored:
            return
        if isinstance(prop.klass, extractors.ClassDef) and prop.klass.generatingInClass:
            prop.klass.generateAfterClass.append(prop)
        elif isinstance(prop.klass, extractors.PyClassDef):
            stream.write('%s%s = property(%s' % (indent, prop.name, prop.getter))
            if prop.setter:
                stream.write(', %s' % prop.setter)
            stream.write(')\n')
        else:
            klassName = prop.klass.pyName or prop.klass.name
            if '.' in prop.getter:
                getter = prop.getter
            else:
                getter = '%s.%s' % (klassName, prop.getter)
            if prop.setter:
                if '.' in prop.setter:
                    setter = prop.setter
                else:
                    setter = '%s.%s' % (klassName, prop.setter)
                
            stream.write("%%Extract(id=pycode%s)\n" % self.module_name)
            stream.write("%s.%s = property(%s" % (klassName, prop.name, getter))
            if prop.setter:
                stream.write(", %s" % setter)
            stream.write(")\n")
            stream.write('%End\n\n')


    #-----------------------------------------------------------------------
    def generatePyFunction(self, pf, stream, indent=''):
        assert isinstance(pf, extractors.PyFunctionDef)
        if len(indent) == 0:
            stream.write('%%Extract(id=pycode%s' % self.module_name)
            if pf.order is not None:
                stream.write(', order=%d' % pf.order)
            stream.write(')\n')
        if pf.deprecated:
            stream.write('%s@wx.deprecated\n' % indent)
        if pf.isStatic:
            stream.write('%s@staticmethod\n' % indent)
        stream.write('%sdef %s%s:\n' % (indent, pf.name, pf.argsString))
        indent2 = indent + ' '*4
        if pf.briefDoc:
            stream.write('%s"""\n' % indent2)
            stream.write(nci(pf.briefDoc, len(indent2)))
            stream.write('%s"""\n' % indent2)
        stream.write(nci(pf.body, len(indent2)))
        if len(indent) == 0:
            stream.write('\n%End\n')
        stream.write('\n')
    
    
    #-----------------------------------------------------------------------
    def generatePyClass(self, pc, stream, indent=''):
        assert isinstance(pc, extractors.PyClassDef)
        if len(indent) == 0:
            stream.write('%%Extract(id=pycode%s' % self.module_name)
            if pc.order is not None:
                stream.write(', order=%d' % pc.order)
            stream.write(')\n')

        # write the class declaration and docstring
        if pc.deprecated:
            stream.write('%s@wx.deprecated\n' % indent)
        stream.write('%sclass %s' % (indent, pc.name))
        if pc.bases:
            stream.write('(%s):\n' % ', '.join(pc.bases))
        else:
            stream.write('(object):\n')
        indent2 = indent + ' '*4
        if pc.briefDoc:
            stream.write('%s"""\n' % indent2)
            stream.write(nci(pc.briefDoc, len(indent2)))
            stream.write('%s"""\n' % indent2)

        # these are the only kinds of items allowed to be items in a PyClass
        dispatch = {
            extractors.PyFunctionDef    : self.generatePyFunction,
            extractors.PyPropertyDef    : self.generatePyProperty,
            extractors.PyCodeDef        : self.generatePyCode,
            extractors.PyClassDef       : self.generatePyClass,
        }
        for item in pc.items:
            item.klass = pc
            f = dispatch[item.__class__]
            f(item, stream, indent2)
 
        if len(indent) == 0:
            stream.write('\n%End\n')
        stream.write('\n')
        
    
    #-----------------------------------------------------------------------
    def generateClass(self, klass, stream, indent=''):
        assert isinstance(klass, extractors.ClassDef)
        if klass.ignored:
            return
        
        # write the class header
        if klass.templateParams:
            stream.write('%stemplate<%s>\n' % (indent, ', '.join(klass.templateParams)))
        stream.write('%s%s %s' % (indent, klass.kind, klass.name))
        if klass.bases:
            stream.write(' : ')
            stream.write(', '.join(klass.bases))
        stream.write(self.annotate(klass))
        stream.write('\n%s{\n' % indent)
        indent2 = indent + ' '*4

        if klass.briefDoc is not None:
            self.generateDocstring(klass, stream, indent2)

        if klass.includes:
            stream.write('%s%%TypeHeaderCode\n' % indent2)
            for inc in klass.includes:
                stream.write('%s    #include <%s>\n' % (indent2, inc))
            stream.write('%s%%End\n\n' % indent2)

        # C++ code to be written to the Type's header 
        if klass.headerCode:
            stream.write("%s%%TypeHeaderCode\n" % indent2)
            for c in klass.headerCode:
                stream.write(nci(c, len(indent2)+4))
            stream.write("%s%%End\n" % indent2)
                
        # C++ code to be written out to the this Type's wrapper code module
        if klass.cppCode:
            stream.write("%s%%TypeCode\n" % indent2)
            for c in klass.cppCode:
                stream.write(nci(c, len(indent2)+4))
            stream.write("%s%%End\n" % indent2)
            
        # is the generator currently inside the class or after it?
        klass.generatingInClass = True 

        # Split the items into public and protected groups
        ctors = [i for i in klass if 
                    isinstance(i, extractors.MethodDef) and 
                    i.protection == 'public' and (i.isCtor or i.isDtor)]
        enums = [i for i in klass if 
                    isinstance(i, extractors.EnumDef) and 
                    i.protection == 'public']
        public = [i for i in klass if i.protection == 'public' and i not in ctors+enums]
        protected = [i for i in klass if i.protection == 'protected']
 
        if klass.kind == 'class':
            stream.write('%spublic:\n' % indent)

        # Write enums first since they may be used as default values in
        # methods or in nested classes
        for item in enums:
            self.dispatchClassItem(klass, item, stream, indent2)
            
        # Next do inner classes
        for item in klass.innerclasses:
            if klass.kind == 'class':
                stream.write('%s%s:\n' % (indent, item.protection))
            item.klass = klass
            self.generateClass(item, stream, indent2)
    
        # and then the ctors and the rest of the items in the class
        for item in ctors:
            self.dispatchClassItem(klass, item, stream, indent2)
            
        for item in public:
            self.dispatchClassItem(klass, item, stream, indent2)

        if protected and [i for i in protected if not i.ignored]:
            stream.write('\nprotected:\n')
            for item in protected:
                self.dispatchClassItem(klass, item, stream, indent2)

        if klass.convertFromPyObject:
            self.generateConvertCode('%ConvertToTypeCode',
                                     klass.convertFromPyObject,
                                     stream, indent + ' '*4)

        if klass.convertToPyObject:
            self.generateConvertCode('%ConvertFromTypeCode',
                                     klass.convertToPyObject,
                                     stream, indent + ' '*4)
            
        stream.write('%s};  // end of class %s\n\n\n' % (indent, klass.name))
        
        # Now generate anything that was deferred until after the class is finished
        klass.generatingInClass = False
        for item in klass.generateAfterClass:
            self.dispatchClassItem(klass, item, stream, indent)
            

        
    def dispatchClassItem(self, klass, item, stream, indent):
        dispatch = {
            extractors.MemberVarDef     : self.generateMemberVar,
            extractors.PropertyDef      : self.generateProperty,
            extractors.PyPropertyDef    : self.generatePyProperty,
            extractors.MethodDef        : self.generateMethod,
            extractors.EnumDef          : self.generateEnum,
            extractors.CppMethodDef     : self.generateCppMethod,
            extractors.CppMethodDef_sip : self.generateCppMethod_sip,
            extractors.PyMethodDef      : self.generatePyMethod,
            extractors.PyCodeDef        : self.generatePyCode,
            extractors.WigCode          : self.generateWigCode,
            }
        item.klass = klass
        f = dispatch[item.__class__]
        f(item, stream, indent)


    def generateConvertCode(self, kind, code, stream, indent):
        stream.write('%s%s\n' % (indent, kind))
        stream.write(nci(code, len(indent)+4))
        stream.write('%s%%End\n' % indent)
        
            
    def generateMemberVar(self, memberVar, stream, indent):
        assert isinstance(memberVar, extractors.MemberVarDef)
        if memberVar.ignored:
            return
        stream.write('%s%s %s' % (indent, memberVar.type, memberVar.name))
        stream.write('%s;\n\n' % self.annotate(memberVar))

        
    def generateProperty(self, prop, stream, indent):
        assert isinstance(prop, extractors.PropertyDef)
        if prop.ignored:
            return
        stream.write('%s%%Property(name=%s, get=%s' % (indent, prop.name, prop.getter))
        if prop.setter:
            stream.write(', set=%s' % prop.setter)
        stream.write(')')
        if prop.briefDoc:
            stream.write(' // %s' % prop.briefDoc)
        stream.write('\n')
        
        
    def generateDocstring(self, item, stream, indent):
        item.pyDocstring = ""
        
        if item.name.startswith('operator'):
            return  # Apparently sip doesn't like operators to have docstrings...
        
        # get the docstring text
        text = nci(extractors.flattenNode(item.briefDoc, False))
        text = wrapText(text)        
        

        #if isinstance(item, extractors.ClassDef):
        #    # append the function signatures for the class constructors (if any) to the class' docstring
        #    try:
        #        ctor = item.find(item.name)
        #        sigs = ctor.collectPySignatures()
        #        if sigs:
        #            text += '\n' + '\n'.join(sigs)
        #    except extractors.ExtractorError:
        #        pass
        #else:
        #    # Prepend function signature string(s) for functions and methods
        #    sigs = item.collectPySignatures()                
        #    if sigs:
        #        if text:
        #            text = '\n\n' + text
        #        text = '\n'.join(sigs) + text
        
        sigs = None
        if isinstance(item, extractors.ClassDef):
            try:
                ctor = item.find(item.name)
                sigs = ctor.collectPySignatures()
            except extractors.ExtractorError:
                pass
        else:
            sigs = item.collectPySignatures()                
        if sigs:
            if text:
                text = '\n\n' + text
            text = '\n'.join(sigs) + text
                
        # write the docstring directive and the text
        stream.write('%s%%Docstring\n' % indent)
        stream.write(nci(text, len(indent)+4))
        stream.write('%s%%End\n' % indent)

        # and save the docstring back into item in case it is needed by other
        # generators later on
        item.pyDocstring = nci(text)

        
    def generateMethod(self, method, stream, indent):
        assert isinstance(method, extractors.MethodDef)
        _needDocstring = getattr(method, '_needDocstring', True)
        checkOverloads = True
        if not method.ignored:
            if method.isVirtual:
                stream.write("%svirtual\n" % indent)
            if method.isStatic:
                stream.write("%sstatic\n" % indent)
            if method.isCtor or method.isDtor:
                stream.write('%s%s(' % (indent, method.name))
            else:
                stream.write('%s%s %s(' % (indent, method.type, method.name))
            if method.items:
                stream.write('\n')
                self.generateParameters(method.items, stream, indent+' '*4)
                stream.write(indent)
            stream.write(')')
            if method.isConst:
                stream.write(' const')
            if method.isPureVirtual:
                stream.write(' = 0')
            stream.write('%s;\n' % self.annotate(method))
                        
            if  _needDocstring and not (method.isCtor or method.isDtor):
                self.generateDocstring(method, stream, indent)
                # We only write a docstring for the first overload, otherwise
                # SIP appends them all together.
                _needDocstring = False
                
            if method.cppCode:
                checkOverloads = False
                code, codeType = method.cppCode
                if codeType == 'sip':
                    stream.write('%s%%MethodCode\n' % indent)
                    stream.write(nci(code, len(indent)+4))
                    stream.write('%s%%End\n' % indent)
                elif codeType == 'function':
                    cm = extractors.CppMethodDef.FromMethod(method)
                    cm.body = code
                    self.generateCppMethod(cm, stream, indent, skipDeclaration=True)
                
            stream.write('\n')
            
        if checkOverloads and method.overloads:
            for m in method.overloads:
                m._needDocstring = _needDocstring
                self.dispatchClassItem(method.klass, m, stream, indent)

            
    def generateCppMethod(self, method, stream, indent='', skipDeclaration=False):
        # Add a new C++ method to a class. This one adds the code as a
        # separate function and then adds a call to that function in the
        # MethodCode directive.
        
        def _removeIgnoredParams(argsString, paramList):
            # if there are ignored parameters adjust the argsString to match
            lastP = argsString.rfind(')')
            args = argsString[:lastP].strip('()').split(',')
            for idx, p in enumerate(paramList):
                if p.ignored:
                    args[idx] = ''
            args = [a for a in args if a != '']
            return '(' + ', '.join(args) + ')'
        
        assert isinstance(method, extractors.CppMethodDef)
        if method.ignored:
            return

        _needDocstring = getattr(method, '_needDocstring', True)
        argsString = _removeIgnoredParams(method.argsString, method.items)
        lastP = argsString.rfind(')')
        pnames = argsString[:lastP].strip('()').split(',')
        for idx, pn in enumerate(pnames):
            # take only the part before the =, if there is one
            name = pn.split('=')[0].strip()   
            # remove annotations
            name = re.sub('/[A-Za-z]*/', '', name) 
            name = name.strip()
            # now get just the part after any space, * or &, which should be
            # the parameter name
            name = re.split(r'[ \*\&]+', name)[-1] 
            pnames[idx] = name
        pnames = ', '.join(pnames)
        typ = method.type

        if not skipDeclaration:
            cppSig = " [ %s ]" % method.cppSignature if method.cppSignature else ""                
            # First insert the method declaration
            if method.isCtor:
                stream.write('%s%s%s%s%s;\n' % 
                             (indent, method.name, argsString, self.annotate(method), cppSig))
            else:
                constMod = " const" if method.isConst else ""
                static = "static " if method.isStatic else ""
                virtual = "virtual " if method.isVirtual else ""                
                pure = " = 0" if method.isPureVirtual else ""
                stream.write('%s%s%s%s %s%s%s%s%s%s;\n' % 
                             (indent, static, virtual, typ, 
                              method.name, argsString, constMod, pure, self.annotate(method), cppSig))
    
            # write the docstring
            if  _needDocstring and not (method.isCtor or method.isDtor):
                self.generateDocstring(method, stream, indent)
                # We only write a docstring for the first overload, otherwise
                # SIP appends them all together.
                _needDocstring = False
                
        klass = method.klass
        if klass:
            assert isinstance(klass, extractors.ClassDef)

        # create the new function
        fstream = Utf8EncodingStream()  # using a new stream so we can do the actual write a little later
        lastP = argsString.rfind(')')
        fargs = argsString[:lastP].strip('()').split(',')
        for idx, arg in enumerate(fargs):
            # take only the part before the =, if there is one
            arg = arg.split('=')[0].strip()   
            arg = arg.replace('&', '*')  # SIP will always want to use pointers for parameters
            arg = re.sub('/[A-Za-z]*/', '', arg)  # remove annotations
            fargs[idx] = arg
        fargs = ', '.join(fargs)
        if method.isCtor:
            klass.cppCtorCount += 1
            fname = '_%s_ctor%d' % (klass.name, klass.cppCtorCount)
            fargs = '(%s)' % fargs
            fstream.write('%s%%TypeCode\n' % indent)
            typ = klass.name
            if method.useDerivedName:
                typ = 'sip'+klass.name
                fstream.write('%sclass %s;\n' % (indent, typ))   # forward declare the derived class
            fstream.write('%s%s* %s%s\n%s{\n' % (indent, typ, fname, fargs, indent))
            fstream.write(nci(method.body, len(indent)+4))
            fstream.write('%s}\n' % indent)
            fstream.write('%s%%End\n' % indent)
            
        else:
            if klass:
                fname = '_%s_%s' % (klass.name, method.name)
                if method.isStatic:
                    # If the method is static then there is no sipCpp to send to
                    # the new function, so it should not have a self parameter.
                    fargs = '(%s)' % fargs
                else:
                    if fargs:
                        fargs = ', ' + fargs
                    selfConst = ''
                    if method.isConst:
                        selfConst = 'const '
                    fargs = '(%s%s* self%s)' % (selfConst, klass.name, fargs)
                fstream.write('%s%%TypeCode\n' % indent)
            else:
                fname = '_%s_function' % method.name
                fargs = '(%s)' % fargs
                fstream.write('%s%%ModuleCode\n' % indent)
            
            # If the return type is in the forcePtrTypes list then make sure
            # that it is a pointer, not a return by value or reference, since
            # SIP almost always deals with pointers to newly allocated
            # objects.
            typPtr = method.type
            if typPtr in forcePtrTypes:
                if '&' in typPtr:
                    typPtr.replace('&', '*')
                elif '*' not in typPtr:
                    typPtr += '*'
        
            fstream.write('%s%s %s%s\n%s{\n' % (indent, typPtr, fname, fargs, indent))
            fstream.write(nci(method.body, len(indent)+4))
            fstream.write('%s}\n' % indent)
            fstream.write('%s%%End\n' % indent)

        # Write the code that will call the new function
        stream.write('%s%%MethodCode\n' % indent)
        stream.write(indent+' '*4)
        if method.isCtor:
            stream.write('sipCpp = %s(%s);\n' % (fname, pnames))
        else:
            stream.write('PyErr_Clear();\n')
            stream.write('%sPy_BEGIN_ALLOW_THREADS\n' % (indent+' '*4))
            stream.write(indent+' '*4)
            if method.type != 'void':
                stream.write('sipRes = ')
            if klass:
                if method.isStatic:
                    # If the method is static then there is no sipCpp to send to
                    # the new function, so it should not have a self parameter.
                    stream.write('%s(%s);\n' % (fname, pnames))
                else:
                    if pnames:
                        pnames = ', ' + pnames
                    stream.write('%s(sipCpp%s);\n' % (fname, pnames))
            else:
                stream.write('%s(%s);\n' % (fname, pnames))
            stream.write('%sPy_END_ALLOW_THREADS\n' % (indent+' '*4))            
            stream.write('%sif (PyErr_Occurred()) sipIsErr = 1;\n' % (indent+' '*4))
        stream.write('%s%%End\n' % indent)

        if method.virtualCatcherCode:
            stream.write('%s%%VirtualCatcherCode\n' % indent)
            stream.write(nci(method.virtualCatcherCode, len(indent)+4))
            stream.write('%s%%End\n' % indent)
            
        # and finally, add the new function itself
        stream.write(fstream.getvalue())
        stream.write('\n')

        if method.overloads:
            for m in method.overloads:
                m._needDocstring = _needDocstring
                self.dispatchClassItem(method.klass, m, stream, indent)
        

        
    def generateCppMethod_sip(self, method, stream, indent=''):
        # Add a new C++ method to a class without the extra generated
        # function, so SIP specific stuff can be done in the function body.
        assert isinstance(method, extractors.CppMethodDef_sip)
        if method.ignored:
            return
        if method.isCtor:
            stream.write('%s%s%s%s;\n' % 
                         (indent, method.name, method.argsString, self.annotate(method)))
        else:
            stream.write('%s%s %s%s%s;\n' % 
                         (indent, method.type, method.name, method.argsString, 
                          self.annotate(method)))
        stream.write('%s%%MethodCode\n' % indent)
        stream.write(nci(method.body, len(indent)+4))
        stream.write('%s%%End\n\n' % indent)

        
        
    def generatePyMethod(self, pm, stream, indent):
        assert isinstance(pm, extractors.PyMethodDef)
        if pm.ignored:
            return
        if pm.klass.generatingInClass:
            pm.klass.generateAfterClass.append(pm)
        else:
            klassName = pm.klass.pyName or pm.klass.name
            stream.write("%%Extract(id=pycode%s)\n" % self.module_name)
            stream.write("def _%s_%s%s:\n" % (klassName, pm.name, pm.argsString))
            pm.pyDocstring = ""
            if pm.briefDoc:
                doc = nci(pm.briefDoc)
                pm.pyDocstring = doc
                stream.write(nci('"""\n%s"""\n' % doc, 4))
            stream.write(nci(pm.body, 4))
            if pm.deprecated:
                stream.write('%s.%s = wx.deprecated(_%s_%s)\n' % (klassName, pm.name, klassName, pm.name))
            else:
                stream.write('%s.%s = _%s_%s\n' % (klassName, pm.name, klassName, pm.name))
            stream.write('del _%s_%s\n' % (klassName, pm.name))
            stream.write('%End\n\n')


    #-----------------------------------------------------------------------

    def annotate(self, item):
        annotations = []
        if item.pyName:
            if not getattr(item, 'wxDropped', False):
                annotations.append('PyName=%s' % item.pyName)

        if isinstance(item, extractors.ParamDef):
            if item.out:
                annotations.append('Out')
            if item.inOut:
                annotations.extend(['In', 'Out'])
            if item.array:
                annotations.append('Array')
            if item.arraySize:
                annotations.append('ArraySize')
            if item.keepReference:
                annotations.append('KeepReference')
                
        if isinstance(item, (extractors.ParamDef, extractors.FunctionDef)):
            if item.transfer:
                annotations.append('Transfer')
            if item.transferBack:
                annotations.append('TransferBack')
            if item.transferThis:
                annotations.append('TransferThis')
            if item.pyInt:
                annotations.append('PyInt')
                
        if isinstance(item, extractors.VariableDef):
            if item.pyInt:
                annotations.append('PyInt')

        if isinstance(item, extractors.TypedefDef):
            if item.noTypeName:
                annotations.append('NoTypeName')

        if isinstance(item, extractors.FunctionDef):
            if item.deprecated:
                annotations.append('Deprecated')
            if item.factory:
                annotations.append('Factory')
            if item.pyReleaseGIL:  
                annotations.append('ReleaseGIL')
            if item.pyHoldGIL:  
                annotations.append('HoldGIL')
            if item.noCopy:
                annotations.append('NoCopy')
            if item.noArgParser:
                annotations.append('NoArgParser')
            
        if isinstance(item, extractors.MethodDef):
            if item.defaultCtor:
                annotations.append('Default')
            if item.noDerivedCtor:
                annotations.append('NoDerived')
            
        if isinstance(item, extractors.ClassDef):
            if item.abstract:
                annotations.append('Abstract')
            if item.allowNone:
                annotations.append('AllowNone')
            if item.deprecated:
                annotations.append('Deprecated')
            if item.external:
                annotations.append('External')
            if item.noDefCtor:
                annotations.append('NoDefaultCtors')
            if item.singlton:
                annotations.append('DelayDtor')
        
        if annotations:
            return '   /%s/' % ', '.join(annotations)
        else:
            return ''

#---------------------------------------------------------------------------
