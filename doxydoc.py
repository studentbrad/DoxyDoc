import sublime
import sublime_plugin

import sublime
import sublime_plugin
import re
import datetime
import getpass

def get_settings():
    return sublime.load_settings("DoxyDoc.sublime-settings")

def get_setting(key, default=None):
    return get_settings().get(key, default)

setting = get_setting

def read_line(view, point):
    """
    @brief      Reads a line.

    @param      view   The view
    @param      point  The point

    @return     The next line
    """
    # if (point >= view.size()):
    #     return

    next_line = view.line(point)

    return view.substr(next_line)

def get_template_args(templ_str):
    """
    @brief      Gets the template arguments.

                Example:
                >>> get_template_args(r'<typename T, typename U>')
                >>> ['T', 'U']
    
    @param      templ_str  The template string

    @return     The template arguments.
    """
    print('Before: {0}'.format(templ_str))

    # remove decltype statements
    templ_str = re.sub(r"decltype\(.+\)", "", templ_str)

    # remove default parameters
    templ_str = re.sub(r"\s*=\s*.+,", ",", templ_str)

    # remove type from template
    templ_str = re.sub(r"[A-Za-z_][\w.<>]*\s+([A-Za-z_][\w.<>]*)", r"\1", templ_str)

    print('After: {0}'.format(templ_str))

    return re.split(r",\s*", templ_str)

def get_function_args(fn_str):
    """
    @brief      Gets the function arguments.

                Example:
                >>> get_function_args(r'bool boolInput, int* pintInput')
                >>> [('bool', 'boolInput'), ('int', 'pintInput')]
    
    @param      fn_str  The function string

    @return     The function arguments.
    """
    print('Before: {0}'.format(fn_str))

    # remove references and pointers
    fn_str = fn_str.replace("&", "")
    fn_str = fn_str.replace("*", "")

    # remove va_list and variadic templates
    fn_str = fn_str.replace("...", "")

    # remove cv-qualifiers
    fn_str = re.sub(r"(?:const|volatile)\s*", "", fn_str)

    # remove namespaces
    fn_str = re.sub(r"\w+::", "", fn_str)

    # remove template arguments in types
    fn_str = re.sub(r"([a-zA-Z_]\w*)\s*<.+?>", r"\1", fn_str)

    # remove parentheses
    fn_str = re.sub(r"\((.*?)\)", r"\1", fn_str)

    # remove arrays
    fn_str = re.sub(r"\[.*?\]", "", fn_str)

    print('After: {0}'.format(fn_str))

    arg_regex = r"(?P<type>[a-zA-Z_]\w*)\s*(?P<name>[a-zA-Z_]\w*)"

    # if there is only one argument
    if ',' not in fn_str:
        # add the type void and an empty string for the name as a tuple
        if ' ' not in fn_str:
            return [("void", "")]
        # add the type and name of the input as a tuple
        else:
            m = re.search(arg_regex, fn_str)
            if m and m.group("type"):
                return [(m.group("type"), m.group("name"))]

    # if there is more than one argument
    result = []
    for arg in fn_str.split(','):
        m = re.search(arg_regex, arg)
        # add the type and name of the input as a tuple
        if m and m.group('type'):
            result.append( (m.group('type'), m.group('name')) )

    return result

class DoxydocCommand(sublime_plugin.TextCommand):
    """
    @brief      Class for DoxyDoc command.
    """
    def set_up(self):
        """
        @brief      Set up function.

                    Implements the settings.
                    Also, creates a dictionary of regular expressions.

        @param      self  The object

        @return     None
        """
        identifier =  r"([a-zA-Z_]\w*)"
        function_identifiers = r"\s*(?:(?:inline|static|constexpr|friend|virtual|explicit|\[\[.+\]\])\s+)*"
        self.command_type = '@' if setting('ccppdoc', True) else '\\'
        self.regexp = {
            'templates': r'\s*template\s*<(.+)>\s*',

            'class': r'\s*(?:class|struct)\s*' + identifier + r'\s*{?',

            'function': function_identifiers + r'(?P<return>(?:typename\s*)?[\w:<>]+)?\s*'
                                               r'(?P<subname>[A-Za-z_]\w*::)?'
                                               r'(?P<name>operator\s*.{1,2}|[A-Za-z_:]\w*)\s*'
                                               r'\((?P<args>[:<>\[\]\(\),.*&\w\s=]*)\).+',

            'constructor': function_identifiers + r'(?P<return>)' # dummy so it doesn't error out
                                                  r'~?(?P<name>[a-zA-Z_]\w*)(?:\:\:[a-zA-Z_]\w*)?'
                                                  r'\((?P<args>[:<>\[\]\(\),.*&\w\s=]*)\).+'
        }

    def write(self, view, string):
        """
        @brief      Write function.

                    Writes a string to the view.

        @param      self    The object
        @param      view    The view
        @param      string  The string

        @return     None
        """
        view.run_command('insert_snippet', {'contents': string })

    def run(self, edit, mode = None):
        """
        @brief      Run function.

                    If the snippet is found, it is added to the view.
                    Otherwise a status message is sent.

        @param      self  The object
        @param      edit  The edit
        @param      mode  The mode

        @return     None
        """
        if setting('enabled', True):
            self.set_up()
            snippet = self.retrieve_snippet(self.view)
            if snippet:
                self.write(self.view, snippet)
            else:
                sublime.status_message('DoxyDoc: Unable to retrieve snippet')

    def retrieve_snippet(self, view):
        """
        @brief      Retrieves a snippet.

        @param      self  The object
        @param      view  The view

        @return     The snippet.
        """
        try:
            # get the point at the begining of the current line
            point = view.sel()[0].begin()

            # get the maximum number of lines
            max_lines = setting('max_lines', 5)

            # read the current line
            current_line = read_line(view, point)

            # find the characters '/**' in the current line
            if (not current_line) or (current_line.find('/**') == -1):
                return '\n * ${0}\n */'

            # increment the point to the end of the current line
            point_prime = point
            point += len(current_line) + 1

            # read the next line
            next_line = read_line(view, point)

            # if the next line does not exist output the characters '*/'
            if not next_line:
                # find the characters '/**' in the current line
                if (current_line.find('/**') == 0) and (point_prime == 3):
                    return self.header_snippet()
                return '\n * ${0}\n */'

            # if the next line is already a comment output the character '*'
            if re.search(r'^\s*\*', next_line):
                return '\n *'

            # search for a template in the next line
            regex_template = re.search(self.regexp['templates'], next_line)
            if regex_template:
                # the following line is either a template function or templated class/struct
                template_args = get_template_args(regex_template.group(1))

                # increment the point to the end of the current line
                point += len(next_line) + 1

                # read the next line
                nnext_line = read_line(view, point)

                # read the function line
                function_line = read_line(view, point)

                # record the point at the end of the function line
                function_endpoint = point + len(function_line) + 1

                # read the next lines up to 'max_lines'
                for x in range(0, max_lines + 1):
                    line = read_line(view, function_endpoint)
                    if not line:
                        break

                    function_line += line
                    function_endpoint += len(line) + 1

                # check if it's a templated constructor or destructor
                regex_constructor = re.match(self.regexp['constructor'], function_line)
                if regex_constructor:
                    return self.template_function_snippet(regex_constructor, template_args)

                # check if it's a templated function
                regex_function = re.match(self.regexp['function'], function_line)
                if regex_function:
                    return self.template_function_snippet(regex_function, template_args)

                # check if it's a templated class
                regex_class = re.match(self.regexp['class'], nnext_line)
                if regex_class:
                    return self.template_snippet(template_args)

            function_lines = ''.join(next_line) # make a copy
            function_endpoint = point + len(next_line) + 1

            for i in range(0, max_lines + 1):
                line = read_line(view, function_endpoint)

                if not line:
                    break

                function_lines += line
                function_endpoint += len(line) + 1

            # check if it's a regular constructor or destructor
            regex_constructor = re.match(self.regexp['constructor'], function_lines)
            if regex_constructor:
                return self.function_snippet(regex_constructor)

            # check if it's a regular function
            regex_function = re.search(self.regexp['function'], function_lines)
            if regex_function:
                return self.function_snippet(regex_function)

            # check if it's a regular class
            regex_class = re.search(self.regexp['class'], next_line)
            if regex_class:
                return self.regular_snippet()

            # find the characters '/**' in the current line
            if (current_line.find('/**') == 0) and (point_prime == 3):
                return self.header_snippet()

            # if all else fails, just send a closing snippet
            return '\n * ${0}\n */'

        except Exception as e:
            # if an error occurs, just send a closing snippet
            return '\n * ${0}\n */'

    def header_snippet(self):
        """
        @brief      Get a header snippet.
        
        @param      self  The object
        
        @return     A header snippet.
        """
        now = datetime.datetime.now()
        snippet = ('\n * {0}brief   ${{1:{{brief description\\}}}}'
                   '\n * {0}details ${{2:{{long description\\}}}}'
                   '\n *'
                   '\n * {0}author  {1}'
                   '\n * {0}date    {2}'
                   '\n */'.format(self.command_type, getpass.getuser(), now.strftime('%b %d, %Y')))

        return snippet

    def regular_snippet(self):
        """
        @brief      Get a regular snippet.

        @param      self  The object

        @return     A regular snippet.
        """
        snippet = ('\n * {0}brief   ${{1:{{brief description\\}}}}'
                   '\n * {0}details ${{2:{{long description\\}}}}'
                   '\n *'
                   '\n */'.format(self.command_type))

        return snippet

    def template_snippet(self, template_args):
        """
        @brief      Get a template snippet.

        @param      self           The object
        @param      template_args  The template arguments

        @return     A template snippet.
        """
        snippet = ('\n * {0}brief   ${{1:{{brief description\\}}}}'
                   '\n * {0}details ${{2:{{long description\\}}}}'
                   '\n *'.format(self.command_type))

        # get the default param margin
        param_margin = setting('default_param_margin', 5)

        # change the param margin to if a tparam length is greater than the default margin
        for tparam_name in template_args:
            if len(tparam_name) > param_margin:
                param_margin = len(tparam_name)

        index = 3
        for tparam_name in template_args:
            len_tparam_name = len(tparam_name)
            snippet += '\n * {0}tparam  {1}{3}  ${{{2}:{{description\\}}}}' \
            .format(self.command_type, tparam_name, index, ' ' * (param_margin - len_tparam_name - 1))
            index += 1

        snippet += '\n */'

        return snippet

    def template_function_snippet(self, regex_obj, template_args):
        """
        @brief      Get a template function snippet.

        @param      self           The object
        @param      regex_obj      The regular expression object
        @param      template_args  The template arguments

        @return     A template function snippet.
        """
        args = regex_obj.group('args')
        function_args = get_function_args(args)

        index = 1
        snippet =  ('\n * {0}brief   ${{{1}:{{brief description\\}}}}'
                    '\n * {0}details ${{{2}:{{long description\\}}}}'
                    '\n *'.format(self.command_type, index, index + 1))
        index += 2

        # get the default param margin
        param_margin = setting('default_param_margin', 5)

        # change the param margin to if a tparam length is greater than the default margin
        for tparam_name in template_args:
            if len(tparam_name) > param_margin:
                param_margin = len(tparam_name)

        # change the param margin to if a tparam length is greater than the default margin
        for _, param_name in function_args:
            if len(param_name) > param_margin:
                param_margin = len(param_name)

        if args and args.lower() != "void":
            for param_type, param_name in function_args:
                if param_type in template_args:
                    template_args.remove(param_type)
                len_param_name = len(param_name)
                snippet += '\n * {0}param   {1}{2}  ${{{3}:{{description\\}}}}' \
                .format(self.command_type, param_name, ' ' * (param_margin - len_param_name), index)
                index += 1

        for tparam_name in template_args:
            len_tparam_name = len(tparam_name)
            snippet += '\n * {0}tparam  {1}{2}  ${{{3}:{{description\\}}}}' \
            .format(self.command_type, tparam_name, ' ' * (param_margin - len_tparam_name - 1), index)
            index += 1

        return_type = regex_obj.group('return')

        if return_type and return_type != 'void':
            snippet += '\n *'
            snippet += '\n * {0}return  ${{{2}:{{description\\}}}}' \
            .format(self.command_type, ' ' * (param_margin - 1), index)

        snippet += '\n */'

        return snippet

    def function_snippet(self, regex_obj):
        """
        @brief      Get a function snippet.

        @param      self       The object
        @param      regex_obj  The regular expression object

        @return     A function snippet.
        """
        fn = regex_obj.group(0)
        args = regex_obj.group('args')
        function_args = get_function_args(args)

        index = 1
        snippet =  ('\n * {0}brief   ${{{1}:{{brief description\\}}}}'
                    '\n * {0}details ${{{2}:{{long description\\}}}}'.format(self.command_type, index, index + 1))
        index += 2

        # get the default param margin
        param_margin = setting('default_param_margin', 5)

        # change the param margin to if a param length is greater than the default margin
        for _, param_name in function_args:
            if len(param_name) > param_margin:
                param_margin = len(param_name)

        if args and args.lower() != 'void':
            snippet += '\n *'
            for _, param_name in function_args:
                len_param_name = len(param_name)
                snippet += '\n * {0}param   {1}{2}  ${{{3}:{{description\\}}}}' \
                .format(self.command_type, param_name, ' ' * (param_margin - len_param_name), index)
                index += 1

        return_type = regex_obj.group('return')

        if return_type and return_type != 'void':
            snippet += '\n *'
            snippet += '\n * {0}return  ${{{2}:{{description\\}}}}' \
            .format(self.command_type, ' ' * (param_margin - 1), index)

        snippet += '\n */'

        return snippet

class DoxygenCompletions(sublime_plugin.EventListener):
    def __init__(self):
        self.command_type = '@' if setting('ccppdoc', True) else '\\'

    def default_completion_list(self):
        return [('author',        'author ${1:{author\}}'),
                ('deprecated',    'deprecated ${1:{deprecated-text\}}'),
                ('exception',     'exception ${1:{exception-object\}} ${2:{description\}}'),
                ('param',         'param ${1:{parameter-name\}} ${2:{description\}}'),
                ('return',        'return ${1:{description\}}'),
                ('see',           'see ${1:{reference\}}'),
                ('since',         'since ${1:{since-text\}}'),
                ('throws',        'throws ${1:{exception-object\}} ${2:{description\}}'),
                ('version',       'version ${1:{version-text\}}'),
                ('code',          'code \n* ${0:{text\}}\n* @endcode'),
                ('bug',           'bug ${1:{bug-text\}}'),
                ('details',       'details ${1:{detailed-text\}}'),
                ('warning',       'warning ${1:{warning-message\}}'),
                ('todo',          'todo ${1:{todo-text\}}'),
                ('defgroup',      'defgroup ${1:{group-name\}} ${2:{group-title\}}'),
                ('ingroup',       'ingroup ${1:{group-name\}}...}'),
                ('addtogroup',    'addtogroup ${1:{group-name\}} ${2:{group-title\}}'),
                ('weakgroup',     'weakgroup ${1:{group-name\}} ${2:{group-title\}}')]

    def on_query_completions(self, view, prefix, locations):
        # only trigger within comments
        if not view.match_selector(locations[0], 'comment'):
            return []

        pt = locations[0] - len(prefix) - 1
        # get character before
        ch = view.substr(sublime.Region(pt, pt + 1))

        flags = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

        # character given isn't '\' or '@'
        if ch != self.command_type:
            return ([], flags)

        return (self.default_completion_list(), flags)
