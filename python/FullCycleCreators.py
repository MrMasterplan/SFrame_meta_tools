###########################################################################
# @Project: SFrame - ROOT-based analysis framework for ATLAS              #
#                                                                         #
# @author Stefan Ask       <Stefan.Ask@cern.ch>           - Manchester    #
# @author David Berge      <David.Berge@cern.ch>          - CERN          #
# @author Johannes Haller  <Johannes.Haller@cern.ch>      - Hamburg       #
# @author A. Krasznahorkay <Attila.Krasznahorkay@cern.ch> - CERN/Debrecen #
# @author S. Heisterkamp   <heisterkamp@nbi.dk>           - Copenhagen    #
# For bugs/comments on this particluar script, please contact the last    #
# autor in the list above                                                 #
###########################################################################


## @package FullCycleCreators
#    @short Functions for creating a new analysis cycle torso
#
# This package collects the functions used by sframe_create_full_cycle.py
# to create the torso of a new analysis cycle. Apart from using
# sframe_create_full_cycle.py, the functions can be used in an interactive
# python session by executing:
#
# <code>
#  >>> import FullCycleCreators
# </code>


import re, sys
import BranchObject
import TTreeReader
import FullCycleTemplates as templates

# pure functions, mostly concerned with text manipulations:
## @short Function to determine whether the type named by typename is an stl_container
#
# C++ Standard Library containers should be cleared at the beginning of the ExecuteEvent
# method when they are used for output. This little function determines if a given typename
# is an stl container using regular expressions.
# 
# @param typename variable type name to evaluate.
def Is_stl_like( typename ):

    import re
    # Check if the typename contains structures like "vector <int>" or similar for list, map or set 
    stl_like = bool( re.search( "(vector|list|set|map)\s*<.*>", typename ) )
    # May want to include other stl_containers here, but I don't expect others to be used.
    # ... and really there is only so far you can go with automatic gode generation.
    if stl_like:
        return "*"
    else:
        return ""

## @short Function to split the cycle name into a namespace and a base-name
#
# The split is done at the last double colon "::". At the moment this only
# produces valid C++ code for up to one layer of namespacing.
#
# @param cycleName Full cycle name to be split
def SplitCycleName( cycleName ):
    """
    splits the cycleName into a class name and a namespace name
    returns a tuple of (namespace, className )
    """
    namespace = ""
    className = cycleName
    if re.search( "::", cycleName ):
        m = re.match( "(.*)::(.*)", cycleName )
        namespace = m.group( 1 )
        className = m.group( 2 )

    return ( namespace, className )

## @short Function to create a backup of a file if it already exits.
# 
# This function checks for the exitence of filename. If it exists, 
# a warning is prined and the filename is moved to a location that has
# .backup appended to the original path.
# 
# @param fileName file path to check
def Backup( filename ):
    """
    Check if the file exists. If it does, beck it up to file+".backup"
    """
    import os.path
    if os.path.exists( filename ):
        print >>sys.stderr, "WARNING:: File \"%s\" already exists" % filename
        print >>sys.stderr, "WARNING:: Moving \"%s\" to \"%s.backup\"" % ( filename, filename )
        import shutil
        shutil.move( filename, filename + ".backup" )

## @short Function to clean up a type name for comparison
# 
# This function takes a c++ type-name and removes unnecessary whitespaces.
# 
# @param typename type-name to clean.
def CleanType( typename ):
    """
    Remove unnecessary whitespaces from the typename
    """
    import re
    typename=re.sub(" (?=<)","",typename) # remove spaces before <
    typename=re.sub("(?<=<) ","",typename) # remove spaces after <
    typename=re.sub(" (?<=>)","",typename) # remove spaces before >
    typename=re.sub("(?<=>) ","",typename) # remove spaces after >
    typename=re.sub("(?<=>)(?=>)"," ",typename) #insert space between >>
    typename = typename.strip()
    return typename



## @short Function creating an analysis cycle header
#
# This function can be used to create the header file for a new analysis
# cycle.
#
# @param className Name of the analysis cycle. Can contain the namespace name.
# @param fileName  Optional parameter with the output header file name
# @param namespace  Optional parameter with the name of the namespace to use
# @param varlist  Optional parameter with a list of "Variable" objects for which to create declarations
# @param create_output  Optional parameter for whether to create declarations for output variables
# @param kwargs Unused.
def CreateHeader( className, headerName = "" , namespace = "", varlist = [], create_output = False, functions=False, **kwargs):
    # Construct the file name if it has not been specified:
    if  not headerName:
        headerName = className + ".h"
    
    fullClassName = className
    if namespace:
        fullClassName = namespace + "::" + className
    formdict = { "class":className, "namespace":namespace, "fullClassName":fullClassName }
    
    # Now create all the lines to declare the input and output variables
    inputVariableDeclarations = ""
    outputVariableDeclarations = ""
    anystl=False
    for var in varlist:
        subs_dict = dict( formdict )
        subs_dict['declare']=var.Declaration()
        subs_dict["commented"]=var.commented
        subs_dict["typename"]=var.typename
        subs_dict["cname"]=var.cname
        anystl = anystl or Is_stl_like( var.typename )
        
        inputVariableDeclarations += "%(declare)s\n" % subs_dict
        
        if create_output:
            outputVariableDeclarations += ("%(type)s\tout_%(cname)s;\n") % {"type":var.StdTypeName(),"cname":var.cname}
    
    if functions:
        formdict[ "functionDeclarations" ] = templates.ConnectInputVariables_declaration
        if create_output:
            formdict[ "functionDeclarations" ] += templates.DeclareOutputVariables_declaration
            if anystl:
                formdict[ "functionDeclarations" ] += templates.ClearOutputVariables_declaration
    else:
        formdict[ "functionDeclarations" ] = ""
    formdict[ "inputVariableDeclarations" ] = inputVariableDeclarations
    formdict[ "outputVariableDeclarations" ] = outputVariableDeclarations
    # Some printouts:
    print "CreateHeader:: Cycle name     = " + className
    print "CreateHeader:: File name      = " + headerName
    
    # Create a backup of an already existing header file:
    Backup( headerName )
    
    # Construct the contents:
    body = templates.header_Body % formdict
    if namespace:
        ns_body = templates.namespace % { "namespace":namespace, "body": templates.Indent( body ) }
    else:
        ns_body = body
    
    full_contents = templates.header_Frame % {"body":ns_body, "capclass":( namespace+"_"+className ).upper(), "fullClassName":namespace+"::"+className}
    
    # Write the header file:
    output = open( headerName, "w" )
    output.write( full_contents )
    output.close()
    
    return headerName


## @short Function creating the analysis cycle source file
#
# This function creates the source file that works with the header created
# by CreateHeader. It is important that CreateHeader is executed before
# this function, as it depends on knowing where the header file is
# physically. (To include it correctly in the source file.)
#
# @param className Name of the analysis cycle
# @param fileName  Optional parameter with the output source file name
# @param namespace  Optional parameter with the name of the namespace to use
# @param varlist  Optional parameter with a list of "Variable" objects to be used by the cycle
# @param create_output  Optional parameter for whether to produce code for output variables
# @param kwargs Unused.
def CreateSource( className, sourceName = "", namespace = "", varlist = [], create_output = False, header = "", functions=False, **kwargs ):
    # Construct the file name if it has not been specified:
    if sourceName == "":
        sourceName = className + ".cxx"
    
    if not header:
        header = className + ".h"
    
    fullClassName = className
    if namespace:
        fullClassName = namespace + "::" + className
    formdict = { "class":className, "namespace":namespace, "fullClassName":fullClassName }
    
    # Determine the relative path of the header using os.path.relpath
    import filesystem,os
    include = filesystem.relpath( header, os.path.dirname( sourceName ) )
    
    # Now create all the lines to handle the variables
    inputVariableConnections = ""
    outputVariableConnections = ""
    outputVariableClearing = ""
    outputVariableFilling = ""
    
    mcBlockOpen=False
    
    for var in varlist:
        subs_dict = dict( formdict )
        subs_dict['declare']=var.Declaration()
        subs_dict["commented"]=var.commented
        subs_dict["typename"]=var.typename
        subs_dict["cname"]=var.cname
        subs_dict["name"]=var.name
        subs_dict["pointer"]=var.pointer
        if var.mc and not mcBlockOpen:
            blockCTRL=templates.StartMCBlock
            mcBlockOpen=True
        elif not var.mc and mcBlockOpen:
            blockCTRL=templates.CloseMCBlock
            mcBlockOpen=False
        else:
            blockCTRL=""
        inputVariableConnections += blockCTRL+"%(commented)sConnectVariable( InTreeName.c_str(), \"%(name)s\", %(cname)s );\n" % subs_dict
        
        if create_output:
            outputVariableConnections += blockCTRL+"%(commented)sDeclareVariable( out_%(cname)s, \"%(name)s\" );\n" % subs_dict
            outputVariableFilling += blockCTRL+"%(commented)sout_%(cname)s = %(pointer)s%(cname)s;\n" % subs_dict
            if var.pointer and Is_stl_like( var.typename ):
                # Not all pointer-accessed types can do this, only stl-vectors                
                outputVariableClearing += "%(commented)sout_%(cname)s.clear();\n" % subs_dict
    
    if mcBlockOpen:
        inputVariableConnections +=templates.CloseMCBlock
        if create_output:
            outputVariableConnections +=templates.CloseMCBlock
            outputVariableFilling +=templates.CloseMCBlock
    
    
    formdict[ "inputVariableConnections" ] = inputVariableConnections
    formdict[ "outputVariableConnections" ] = outputVariableConnections
    formdict[ "outputVariableClearing" ] = outputVariableClearing
    formdict[ "outputVariableFilling" ] = outputVariableFilling
    
    formdict[ "functionBodys" ] = ""
    
    if functions:
        formdict[ "functionBodys" ]+=templates.ConnectInputVariables_body%formdict
        formdict[ "inputVariableConnections" ] = templates.ConnectInputVariables_call
        
        if create_output:
            formdict[ "functionBodys" ]+=templates.DeclareOutputVariables_body%formdict
            formdict[ "outputVariableConnections" ] = templates.DeclareOutputVariables_call
        
            if outputVariableClearing:
                formdict[ "functionBodys" ]+=templates.ClearOutputVariables_body%formdict
                formdict[ "outputVariableClearing" ] = templates.ClearOutputVariables_call
        
        
    
    
    # Some printouts:
    print "CreateSource:: Cycle name     =", className
    print "CreateSource:: File name      =", sourceName
    
    # Create a backup of an already existing source file:
    Backup( sourceName )
    
    #Construct the contents of the source file:
    body = templates.source_Body % formdict
    if namespace:
        ns_body = templates.namespace % { "namespace":namespace, "body":templates.Indent( body ) }
    else:
        ns_body = body
    full_contents = templates.source_Frame % { "body":ns_body, "fullClassName":fullClassName, "header":include }
    
    
    # Write the source file:
    output = open( sourceName, "w" )
    output.write( full_contents )
    output.close()
    return


## @short Function adding link definitions for rootcint
#
# Each new analysis cycle has to declare itself in a so called "LinkDef
# file". This makes sure that rootcint knows that a dictionary should
# be generated for this C++ class.
#
# This function is also quite smart. If the file name specified does
# not yet exist, it creates a fully functionaly LinkDef file. If the
# file already exists, it just inserts one line declaring the new
# cycle into this file.
#
# @param className Name of the analysis cycle. Can contain the namespace name.
# @param linkdefName  Optional parameter with the LinkDef file name
# @param namespace  Optional parameter with the name of the namespace to use
# @param kwargs Unused.
def AddLinkDef( className, linkdefName = "LinkDef.h" , namespace = "", varlist = [], **kwargs):
    
    cycleName = className
    if namespace:
        cycleName = namespace + "::" + className
    
    new_lines = "#pragma link C++ class %s+;\n" %  cycleName
    
    # Find all object-like variable types and make pragma lines for them
    # This is unnecessary for many simple vectors, but since it doesn't
    # do any harm, We might as well include it for all object types
    ignores=set([CleanType("vector<int>"), 
                CleanType("vector<float>"),
                CleanType("vector<short>"),
                CleanType("vector<unsigned short>"),
                CleanType("vector<unsigned int>"),
                CleanType("vector<double>")])
    import re,os.path
    if os.path.exists( linkdefName ):
        for match in re.finditer("""#pragma link C\+\+ class (?P<type>.*?)\+;""",open(linkdefName).read()):
            ignores.add(CleanType(match.group("type")))
    types = set()
    for var in varlist:
        if var.pointer:
            if var.typename not in ignores:
                types.add( var.typename )
    
    for typename in types:
        new_lines += "#pragma link C++ class %s+;\n" % typename
    
    import os.path
    if os.path.exists( linkdefName ):
        print "AddLinkDef:: Extending already existing file \"%s\"" % linkdefName
        # Read in the already existing file:
        infile = open( linkdefName, "r" )
        text = infile.read()
        infile.close()
        
        # Find the "#endif" line:
        if not re.search( """#endif""", text ):
            print >>sys.stderr, "AddLinkDef:: ERROR File \"%s\" is not in the right format!" % linkdefName
            print >>sys.stderr, "AddLinkDef:: ERROR Not adding link definitions!"
            return
        
        # Overwrite the file with the new contents:
        output = open( linkdefName, "w" )
        #Insert the newlines before the #endif
        # """(?=\n#endif)""" matches the empty string that is immediately succeded by \n#endif
        output.write( re.sub( """(?=\n#endif)""", new_lines+"\n", text ) )
        output.close()
        
    else:
        # Create a new file and fill it with all the necessary lines:
        print "AddLinkDef:: Creating new file called \"%s\"" % linkdefName
        output = open( linkdefName, "w" )
        output.write( templates.LinkDef %{ "new_lines":new_lines } )
    
    return


## @short Function creating a configuration file for the new cycle
#
# This function uses the configuration file in $SFRAME_DIR/user/config/FirstCycle_config.xml
# and adapts it for this analysis using PyXML. As this file is expected to
# change in future updates this function may break. It may therefore be better to create something from scratch.
# The advantage of this approach is that the resulting xml file works, and still
# contains all the comments of FirstCycle_config.xml, making it more suitabel for beginners.
# 
#
# @param className Name of the analysis cycle
# @param configName  Optional parameter with the output config file name
# @param namespace  Optional parameter with the name of the namespace to use
# @param analysis  Optional parameter with the name of the analysis package
# @param rootfile  Optional parameter with the name of an input root-file
# @param treename  Optional parameter with the name of the input tree
# @param outtree  Optional parameter with the name of the output tree if desired
# @param kwargs Unused.
def CreateConfig( className, configName = "" , namespace = "", analysis = "MyAnalysis", rootfile = "my/root/file.root", treename = "InTreeName", outtree = "", dataType="DATA", **kwargs):
    # Construct the file name if it has not been specified:
    if configName == "":
        configName = className + "_config.xml"
    Backup( configName )
    
    cycleName = className
    if namespace:
        cycleName =namespace + "::" + cycleName
    
    # Some printouts:
    print "CreateConfig:: Cycle name     =", className
    print "CreateConfig:: File name      =", configName
    
    # Use the configuration file FirstCycle_config.xml as a basis:
    import os
    xmlinfile = os.path.join( os.getenv( "SFRAME_DIR" ), "user/config/FirstCycle_config.xml" )
    if not os.path.exists( xmlinfile ):
        print  >>sys.stderr, "ERROR: Expected to find example configuration at", xmlinfile
        print  >>sys.stderr, "ERROR: No configuration file will be written."
        return
    
    #Make changes to adapt this file to our purposes
    try:
        import xml.dom.minidom
        dom = xml.dom.minidom.parse( open( xmlinfile ) )
        
        nodes = dom.getElementsByTagName( "JobConfiguration" )
        # If more than one Job configuration exists, crash
        if not len( nodes ) == 1: raise AssertionError("More than one JobConfiguration section in %s"%xmlinfile)
        JobConfiguration = nodes[ 0 ]
        JobConfiguration.setAttribute( "JobName", className + "Job" )
        JobConfiguration.setAttribute( "OutputLevel", "INFO" )
        
        #Find the libSFrameUser library and change it to ours
        for node in dom.getElementsByTagName( "Library" ):
            if node.getAttribute( "Name" ) == "libSFrameUser":
                node.setAttribute( "Name", "lib" + analysis )
                newnode=node.cloneNode(deep=True)
                newnode.setAttribute( "Name", "libSFrameMetaTools" )
                JobConfiguration.insertBefore(dom.createComment(" Uncomment if you want to use compiled features of SFrameMetaTools: "), node)
                JobConfiguration.insertBefore(dom.createComment(newnode.toxml()), node)
                # JobConfiguration.insertBefore(newnode,node)
        
        #Find the SFrameUser package and change it to ours
        for node in dom.getElementsByTagName( "Package" ):
            if node.getAttribute( "Name" ) == "SFrameUser.par":
                node.setAttribute( "Name", analysis + ".par" )
                newnode=node.cloneNode(deep=True)
                newnode.setAttribute( "Name", "SFrameMetaTools.par" )
                JobConfiguration.insertBefore(dom.createComment(" Uncomment if you want to use compiled features of SFrameMetaTools: "), node)
                JobConfiguration.insertBefore(dom.createComment(newnode.toxml()), node)
                # JobConfiguration.insertBefore(newnode,node)
                
        
        nodes = dom.getElementsByTagName( "Cycle" )
        #There should be exactly one cycle
        if not len( nodes ) == 1: raise AssertionError("More than one Cycle section in %s"%xmlinfile)
        cycle = nodes[ 0 ]
        cycle.setAttribute( "Name", cycleName )
        cycle.setAttribute( "RunMode", "LOCAL" )
        
        #Remove all but one input data
        while len( dom.getElementsByTagName( "InputData" ) ) > 1:
            cycle.removeChild( dom.getElementsByTagName( "InputData" )[ -1 ] )
        inputData = dom.getElementsByTagName( "InputData" )[ 0 ]
        
        for i in range( inputData.attributes.length ):
            inputData.removeAttribute( inputData.attributes.item( 0 ).name )
        
        inputData.setAttribute( "Lumi", "1.0" )
        inputData.setAttribute( "Version", "V1" )
        inputData.setAttribute( "Type", dataType )
        # inputData.setAttribute( "Cacheable", "False" )
        # inputData.setAttribute( "NEventsMax", "-1" )
        # inputData.setAttribute( "NEventsSkip", "0" )
        
        # Remove all but one input files
        while len( inputData.getElementsByTagName( "In" ) ) > 1:
            inputData.removeChild( inputData.getElementsByTagName( "In" )[ -1 ] )
        In = inputData.getElementsByTagName( "In" )[ 0 ]
        
        In.setAttribute( "Lumi", "1.0" )
        In.setAttribute( "FileName", rootfile )
        
        # Remove all but one input trees
        while len( inputData.getElementsByTagName( "InputTree" ) ) > 1:
            inputData.removeChild( inputData.getElementsByTagName( "InputTree" )[ -1 ] )
        InputTree = inputData.getElementsByTagName( "InputTree" )[ 0 ]
        
        InputTree.setAttribute( "Name", treename )
        
        # Remove the MetadataOutputTrees
        while len( inputData.getElementsByTagName( "MetadataOutputTree" ) ):
            inputData.removeChild( inputData.getElementsByTagName( "MetadataOutputTree" )[ 0 ] )
        
        # Remove all but one output Trees
        while len( inputData.getElementsByTagName( "OutputTree" ) )>1:
            inputData.removeChild( inputData.getElementsByTagName( "OutputTree" )[ -1 ] )
        outtreenode = inputData.getElementsByTagName( "OutputTree" )[ 0 ]
        
        if not outtree:
            # No output is desired, remove this node
            inputData.removeChild( outtreenode )
        else:
            outtreenode.setAttribute( "Name", outtree )
        
        nodes = cycle.getElementsByTagName( "UserConfig" )
        # We expect one UserConfig section
        if not len( nodes ) == 1: raise AssertionError
        UserConfig = nodes[ 0 ]
        
        # Remove all but one item
        while len( UserConfig.getElementsByTagName( "Item" ) ) > 1:
            UserConfig.removeChild( UserConfig.getElementsByTagName( "Item" )[ -1 ] )
        Item = UserConfig.getElementsByTagName( "Item" )[ 0 ]
        
        Item.setAttribute( "Name", "InTreeName" )
        Item.setAttribute( "Value", treename )
        
    except AssertionError:
        # If any exceptions were raised, the FirstCycle_config.xml file
        # has probably changed. In that case this function should be 
        # updated to reflect that change.
        print "ERROR: ", xmlinfile, "has an unexpected structure."
        print "ERROR: No configuration file will be written."
        return
    
    # For some reason toprettyxml inserts lines of whitespaces.
    # Use some regexp to get rid of those
    text = re.sub( """(?<=\n)([ \t]*\n)+""", "", dom.toprettyxml( encoding ="UTF-8" ) )
    outfile =open( configName, "w" )
    outfile.write( text )
    outfile.close()
    return


## @short Function to add a JobConfig file to the analysis
#
# A JobConfig.dtd file is necessary for parsing the config xml files.
# Use the one from the $SFRAME_DIR/user/ example if there isn't one 
# here already.
#
# @param directory The name of the directory where the file should be
# @param kwargs Unused.
def AddJobConfig( config_directory, **kwargs):
    import os.path
    newfile = os.path.join( config_directory, "JobConfig.dtd" )
    if os.path.exists( newfile ):
        print "Keeping existing JobConfig.dtd"
        return
    
    oldfile = os.path.join( os.getenv( "SFRAME_DIR" ), "user/config/JobConfig.dtd" )
    if not os.path.exists( oldfile ):
        print "ERROR: Expected JobConfig.dtd file at", oldfile
        print "ERROR: JobConfig.dtd file not copied"
        return
        
    import shutil
    shutil.copy( oldfile, newfile )
    print "Using a copy of", oldfile


## @short Function to obtain the name of the analysis
#
# The name of the analysis can be obtained in one of three ways:
# by checking the name of the current directory
# by reading the Makefile
# by checking the name of a linkDef file.
# Returns the name of the analysis. Throws an error if inconsistencies arise.
def GetAnalysisName():
    import os.path
    
    # 1. name of the cwd:
    name_dir = os.path.basename( os.getcwd() )
    
    # 2. name specified in the makefile:
    import re
    name_make = ""
    if os.path.exists("Makefile"):
        makeconts=open("Makefile").read()
        match=re.search(r"LIBRARY[ \t]*=[ \t]*(?P<name>[a-zA-Z][a-zA-Z0-9_]*)",makeconts)
        if match:
            name_make = match.group("name")
    if not name_make:
        print "WARNING: unable to find the analysis name in the Makefile."
        print """WARNING: ... was looking for a line like "LIBRARY = MyAnalysis" """
    
    # 3. name of linkdef
    import glob
    name_linkdef=""
    linkdefs=glob.glob("include/*_LinkDef.h")
    if len(linkdefs)==1:
        name_linkdef=linkdefs[0][8:-10]
    if not name_linkdef:
        print "WARING: unable to get the name of the analysis from the *_LinkDef.h file"
        if linkdefs:
            print "WARING: ... there wasn't a unique one."
        else:
            print "WARING: ... there wasn't one."
    
    if name_dir==name_make and name_dir==name_linkdef:
        return name_dir
    else:
        print """ERROR: Found conflicting names for this analysis. Please specify the correct name with the -a option. """
        print """ERROR: ... found "%s", "%s" and "%s". """ %(name_dir,name_make,name_linkdef)
        import sys
        sys.exit(-1)
    # print "dir :",name_dir
    # print "make:",name_make
    # print "def :",name_linkdef

## @short Main analysis cycle creator function
#
# The users of this class should normally just use this function
# to create a new analysis cycle.
#
# It only really needs to receive the name of the new cycle, it can guess
# the values of all the oter parameters. It calls all the
# other functions of this class to create all the files for the new
# cycle.
#
# @param cycleName Name of the analysis cycle. Can contain the namespace name.
# @param linkdef Optional parameter with the name of the LinkDef file
# @param rootfile Optional parameter with the name of a rootfile containing a TTree
# @param treename Optional parameter with the name of the input TTree
# @param varlist Optional parameter with a filename for a list of desired variable declarations
# @param outtree Optional parameter with the name of the output TTree
# @param analysis Optional parameter with the name of analysis package
def CreateCycle( cycleName, linkdef = "", rootfile = "", treename = "", varlist = "", outtree = "", analysis = "", mctags="mc_,truth", functions=False ):
    
    namespace, className = SplitCycleName( cycleName )
        
    # Make sure analysis is set
    if not analysis:
        analysis = GetAnalysisName()
        print "Using analysis name \"%s\"" % analysis
    
    #First we take care of all the variables that the user may want to have read in.
    # If treename wasn't given, it can be read from the rootfile if it exits.
    if not treename:
        treename = TTreeReader.GetTreeName( rootfile ) # gives default if rootfile is empty
    
    # The three parameters related to the input variables are varlist, treename and rootfile.
    # if neither rootfile or varlist are given, no input variable code will be written.
    cycle_variables = []
    # Prefer to read the input from the varlist
    if varlist:
        cycle_variables = BranchObject.ReadVariableSelection( varlist )
    elif rootfile:
        cycle_variables = TTreeReader.ReadVars( rootfile, treename )
    
    # The list of input variables is now contained in cycle_variables
    # if this list is empty, the effect of this class should be identical to that of the old CycleCreators
    
    #now do the MC-tagging
    import re
    mcmatch=[]
    for tag in mctags.split(','):
        tag=tag.strip()
        if not tag:
            continue
        try:
            pat=re.compile(tag,re.IGNORECASE)
        except:
            print >>sys.stderr, "Not a valid expression for mc-tagging:",tag
            continue
        mcmatch.append(pat)
    
    anymc=False
    for var in cycle_variables:
        anymatch = reduce(lambda a,b: a or b,[m.search(var.name) for m in mcmatch])
        anymc = anymc or anymatch
        if anymatch:
            var.mc=1
            var.title+="MC"
    
    if anymc:
        dataType="MC"
    else:
        dataType="DATA"
    
    #From now on rootfile is only used in the config file:
    if not rootfile:
        rootfile ="your/input/file.root"
    
    # Check if a directory called "include" exists in the current directory.
    # If it does, put the new header in that directory, otherwise, put it in the current directory
    import os.path
    include_dir = "include/"
    if not os.path.exists( include_dir ):
        include_dir = ""
        
    if not linkdef:
        linkdef = include_dir+analysis+"_LinkDef.h"
        # import glob
        # filelist = glob.glob( include_dir+"*LinkDef.h" )
        # if len( filelist ) == 0:
        #     print "CreateCycle:: WARNING There is no LinkDef file under", include_dir
        #     linkdef = include_dir+"LinkDef.h"
        #     print "CreateCycle:: WARNING Creating one with the name", linkdef
        # elif len( filelist ) == 1:
        #     linkdef = filelist[ 0 ]
        # else:
        #     print "CreateCycle:: ERROR Multiple header files ending in LinkDef.h"
        #     print "CreateCycle:: ERROR I don't know which one to use..."
        #     return
    
    # Check if a directory called "src" exists in the current directory.
    # If it does, put the new source in that directory, otherwise, put it in the current directory
    src_dir = "src/"
    if not os.path.exists( src_dir ):
        src_dir = ""

    # Check if a directory called "config" exists in the current directory.
    # If it does, put the new configuration in that directory. Otherwise leave it up
    # to the CreateConfig function to put it where it wants.
    config_dir = "config/"
    if not os.path.exists( config_dir ):
        config_dir = ""
    
    
    # All options seem to be in order. Generate the code.
    options = dict()
    options[ "className" ]=className
    options[ "namespace" ] = namespace
    options[ "varlist" ] = cycle_variables
    options[ "create_output" ] = bool( outtree )
    options[ "headerName" ] = include_dir + className + ".h"
    options[ "linkdefName" ] = linkdef
    options[ "sourceName" ] = src_dir + className + ".cxx"
    options[ "configName" ] = config_dir + className + "_config.xml"
    options[ "analysis" ] = analysis
    options[ "rootfile" ] = rootfile
    options[ "dataType" ] = dataType
    options[ "treename" ] = treename
    options[ "outtree" ] = outtree
    options[ "config_directory" ] = config_dir
    options[ "functions" ] = True #functions
    options[ "header" ] = CreateHeader( **options )
    AddLinkDef( **options )
    CreateSource( **options )
    CreateConfig( **options )
    AddJobConfig( **options )
    print "Please indent the code using your favourite formatter like 'Artistic Style' (astyle)."
    return
