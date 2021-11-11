import json
import hashlib
import pandas as pd
import re
import lib_globals as g
import lib_ohlc as o

# + -------------------------------------------------------------
# + CLASSES
# + -------------------------------------------------------------
class Gvars:
    def __init__(self):
        self.counter = -1
        self.idx = 0
        self.reload_ohlcv = True
        self.ma_low_holding = False
        self.ma_low_sellat = False
        self.cur = False



class Cvars:
    def __init__(self, cfgfile):
        self.cfgfile = cfgfile
        self.this_md5 = ""
        fdata = self.get_json_from_file(self.cfgfile)
        # * save clean version of json
        outfile = open(f'_lastloaded_{g.instance_num}.json', 'w')
        outfile.write(fdata)
        outfile.close()

        try:
            self.conf = json.loads(fdata)
        except  Exception as ex:
            print("----------------------------------------------------------")
            print(f"Error reading {self.cfgfile}.")
            print(f"An exception of type {ex} occurred. Arguments:\n{ex.args}")
            print(f"Try linting '_lastloaded_{g.instance_num}.json' at 'https://jsonlint.com/")
            print("COMMON ERRORS: 'True' vs 'true', missing or extra comma, garbage at bottom or some accidental text.")
            print("----------------------------------------------------------")
            o.waitfor()
            exit(1)
        self.this_md5 = hashlib.md5(str(fdata).encode('utf-8')).hexdigest()

    def save(self,df,filename):
        df.to_json(filename, orient='split', compression='infer', index='true')
        g.logit.debug(f"Saving to file: {filename}")

    def load(self,filename, **kwargs):
        df = pd.read_json(filename, orient='split', compression='infer')
        try:
            g.logit.debug(f"Trimming df to {kwargs['maxitems']}")
            df = df.head(self.get("datalength"))
        except:
            pass
        return(df)

    def csave(self,data,filename):
        # + fp = fn.split(".")
        # + filename = f"{fp[0]}_{g.instance_num}.{fp[1]}"
        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4)
        g.logit.debug(f"Common Saving to file: {filename}")

    def cload(self,filename):
        # + fp = fn.split(".")
        # + filename = f"{fp[0]}_{g.instance_num}.{fp[1]}"
        with open(filename) as json_file:
            data = json.load(json_file)
        return data

    def get(self, varname=""):
        if varname == "":
            return self.conf
        try:
            varval =self.conf[varname]
            if varname == "since":
                p = varval.split(":")
                if p[1] == "h":
                    varval = int(p[0])
                if p[1] == "d":
                    varval = int(int(p[0])*24)
                if p[1] == "m":
                    varval = int(int(p[0])/60)
                # + print("since (hours)",varval)
                return varval
            return varval
        except:
            # + key not found
            # + print(f"<{varname} = False>")
            return False

    # + def put(self, varname, value):
    # + jary = self.get()
    # + varval =self.conf[varname]
    # + if varname == "since":
    # + p = varval.split(":")
    # + if p[1] == "h":
    # + varval = int(p[0])
    # + if p[1] == "d":
    # + varval = int(int(p[0])*24)
    # + if p[1] == "m":
    # + varval = int(int(p[0])/60)
    # + # + print("since (hours)",varval)
    # + return varval
    # + return varval
    # + except:
    # + # + key not found
    # + # + print(f"<{varname} = False>")
    # + return False

    @staticmethod
    def get_json_from_file(filepath):
        contents = ""
        fh = open(filepath)
        for line in fh:

            # cleaned_line = line.split("//", 1)[0]
            cleaned_line = re.split('//|#', line)[0]
            if len(cleaned_line) > 0 and line.endswith("\n") and "\n" not in cleaned_line:
                cleaned_line += "\n"
            contents += cleaned_line
        while "/*" in contents:
            pre_comment, post_comment = contents.split("/*", 1)
            contents = pre_comment + post_comment.split("*/", 1)[1]
            # nc = ""
            # for line in contents:
            #     if line != "\n\n":
            #         nc = nc + line
            # return nc
        return contents
