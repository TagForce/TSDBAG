'''
Created on 12 nov. 2024

@author: Raymond Sagius
'''

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import csv, os.path, sys



def check_files(job, batchtable):
    
    csvfiles = ''
    expfile = ''
    # Check for output folder and duplicate export filenames
    if 'fnexp' in job.keys():
        if job['fnexp'] in batchtable.keys():
            csvfiles = job['fnexp']
            filelist = []
            for fn in batchtable[csvfiles]:
                if fn not in filelist:
                    if os.path.isdir(os.path.dirname(fn)):
                        filelist.append(fn)
                    else:
                        return {"error": "Export folder not found. Please make sure '{0}' exists and is writable.".format(os.path.dirname(fn))}
                else:
                    return {"error": "Duplicate export filename ({0}) found in CSV, exiting, because this will result in overwritten output".format(fn)}
        else:
            if len(batchtable) > 0:
                return {"error": "Column name {0} not found in the CSV.".format(job['fnexp'])}
            if os.path.isdir(os.path.dirname(job['fnexp'])):
                expfile = job['fnexp']
            else:
                return {"error": "Export folder not found. Please make sure {0} exists and is writable.".format(os.path.dirname(job['fnexp']))}
                
    # Loop through each command and check for file availability
    if 'commands' not in job.keys():
        return {"error":"No commands in job definition. Nothing to do."}
    else:
        commands = job['commands']
        for command in commands:
            filenames = []
            ctype = list(command)[0]
            match ctype:
                case 'overlay':
                    if not os.path.isfile(command[ctype]['image']):
                        return {"error":"Overlay file {0} not found. Make sure any referenced overlays exist.".format(command[ctype]['image'])}
                case 'boverlay':
                    if not os.path.isfile(command[ctype]['image']):
                        if not command[ctype]['image'] in batchtable.keys():
                            return {"error":"Boverlay column '{0}' not found. Exiting.".format(command[ctype]['image'])}
                        else:
                            for fp in batchtable[command[ctype]['image']]:
                                if not os.path.isfile(fp) and fp != '':
                                    return {"error":"Overlay file {0} not found. Make sure any referenced overlays exist.".format(fp)}
                    else:
                        return {"error":"Boverlay has a direct file reference to '{0}'. Use 'overlay' instead.".format(command[ctype]['image'])}
                case 'text':
                    if not os.path.isfile(command[ctype]['font']):
                        return {"error":"Font file {0} not found. Make sure any referenced fonts exist.".format(command[ctype]['font'])}    
                case 'btext':
                    if not os.path.isfile(command[ctype]['font']):
                        if not command[ctype]['image'] in batchtable.keys():
                            return {"error":"Font column or file '{0}' not found. Exiting.".format(command[ctype]['font'])}
                        else:
                            for fp in batchtable[command[ctype]['font']]:
                                if not os.path.isfile(fp) and fp != '':
                                    return {"error":"Overlay file {0} not found. Make sure any referenced overlays exist.".format(fp)}    
    return {}


def check_csv(job):
    
    batchtable = {}
    headers = []
    if 'csvfile' in job.keys():
        if os.path.isfile(job['csvfile']):
            try:
                with open(job['csvfile']) as csvfile:
                    csvdata = csv.reader(csvfile, delimiter=',', quotechar='"')
                    csvtable = []
                    for row in csvdata:
                        csvtable.append(row)
                    batchcount = len(csvtable) - 1
            except Exception as e:
                return {"error":"Error reading csv file: {0}".format(e)}
            if batchcount > 0:    
                for item in csvtable[0]:
                    batchtable[item] = []
                    headers.append(item)
                cnt = 1
                while cnt < len(csvtable):
                    rc = 0
                    while rc < len(csvtable[cnt]):
                        batchtable[headers[rc]].append(csvtable[cnt][rc])
                        rc += 1
                    cnt += 1
    return batchtable



def sort_commands(commandlist):
    
    results = []
    for command in commandlist:
        name = list(command)[0]
        if len(results) == 0:
            results.append(command)
            continue
        else:
            for result in results:
                resname = list(result)[0]
                if int(command[name]['order']) < int(result[resname]['order']):
                    results.insert(results.index(result), command)
                    break
            if command not in results:
                results.append(command)
    return results


# Add an image on top of the artwork
def add_overlay(art, img, pos):
    
    if img == '': # Image value is empty for this overlay, skip it.
        return art
    print("Adding image {0} to artwork at position ({1}, {2})".format(img, pos[0], pos[1]))
    result = art
    ol = Image.open(img)
    result.paste(ol, pos, ol)
    return result



# Add text on top of the artwork
def add_text(art, text, font, size, just, pos, rotation, textcolor, dropshadow, dropcolor):
    
    dropshadow = dropshadow == "True"
    if text == '': # Text value is empty for this layer, skip it.
        return art
    print("Adding '{0}' to the artwork using the following configuration:\nfont: {1}\nposition: ({2}, {3})\nrotation: {4} degrees\ncolor: {5}\ndropshadow: {6}\ndropcolor: {7}".format(text, font, pos[0], pos[1], rotation, textcolor, dropshadow, dropcolor))
    result = art
    ol = ImageDraw.Draw(result)
    font = ImageFont.truetype(font, size)
    match just:
        case "left":
            anchor = 'ls'
        case "right":
            anchor = 'rs'
        case "center" | "centre":
            anchor = 'ms'
        case _:
            anchor = 'ls'
    # Create the drop shadow first if true:
    if dropshadow:
        drop = drop_shadow(result, pos, text, dropcolor, font, anchor)
        result.paste(drop, drop)
    
    # Now place the text
    ol.text(pos, text, fill=(textcolor['r'], textcolor['g'], textcolor['b']), font=font, anchor=anchor)
    return result

def drop_shadow(art, pos, text, color, font, anchor):
    
    drop = Image.new('RGBA', art.size)
    draw = ImageDraw.Draw(drop)
    draw.text(pos, text, fill=(color['r'], color['g'], color['b']), font=font, anchor=anchor)
    for i in range(7):
        drop = drop.filter(ImageFilter.BLUR)
    return drop
    
    
# This checks the job descriptions for validity and ultimately renders the image to return.
def generate_art(job):
    
    result = {}
    artsize = [0,0] # start with a 0-size canvas
    arttype = list(job)[0]
    
    # Determine the type of artwork we're creating
    match arttype:
        case "poster":
            artsize = [680, 1000]
        case "thumb":
            artsize = [1280, 720]
        case "banner":
            artsize = [1000, 185]
        case "square":
            artsize = [700, 700]
        case _:
            return {'error': "'{0}' is not a valid art type".format(arttype)}
    result['artsize'] = artsize
    
    # If there is a csvfile for batch execution, try to read it. 
    batchtable = check_csv(job[arttype])
    if 'error' in batchtable.keys():
        return batchtable
    
    # Determine where the exports go. Make sure we can export the file(s).
    chk = check_files(job[arttype], batchtable)
    if 'error' in chk.keys():
        return chk
    
    # Sort the list of commands by order. This is to fix the order, in case the list isn't ordered on a system.
    job[arttype]['commands'] = sort_commands(job[arttype]['commands'])
    
    # Determine the runcounts
    if len(batchtable) > 0:
        batchcount = len(batchtable[list(batchtable)[0]])
    else:
        batchcount = 0
        
    # Start running each image export
    runcount = 0
    while True:
        art = Image.new("RGBA", artsize, "black")
        for command in job[arttype]['commands']:
            func = list(command)[0] 
            match func:
                case "overlay":
                    art = add_overlay(
                        art, 
                        command[func]['image'], 
                        [command[func]['pos']['x'], command[func]['pos']['y']])
                case "boverlay":
                    art = add_overlay(
                        art, 
                        batchtable[command[func]['image']][runcount], 
                        [command[func]['pos']['x'], command[func]['pos']['y']])
                case "text":
                    art = add_text(
                        art, 
                        command[func]['text'], 
                        command[func]['font'],
                        command[func]['size'],
                        command[func]['just'],
                        [command[func]['pos']['x'], command[func]['pos']['y']], 
                        command[func]['rot'],
                        command[func]['color'],
                        command[func]['drop'],
                        command[func]['dcol'])
                case "btext":
                    art = add_text(
                        art, 
                        batchtable[command[func]['text']][runcount], 
                        command[func]['font'], 
                        command[func]['size'],
                        command[func]['just'],
                        [command[func]['pos']['x'], command[func]['pos']['y']], 
                        command[func]['rot'],
                        command[func]['color'],
                        command[func]['drop'],
                        command[func]['dcol'])
        if batchcount == 0:
            print("Exporting to {0}".format(job[arttype]['fnexp']))
            art = art.convert("YCbCr")
            with open(job[arttype]['fnexp'], 'wb') as fp:
                art.save(fp, "JPEG", quality=95, optimize=True)
        else:
            print("Exporting to {0}".format(batchtable[job[arttype]['fnexp']][runcount]))
            art = art.convert("YCbCr")
            with open(batchtable[job[arttype]['fnexp']][runcount], 'wb') as fp:
                art.save(fp, "JPEG", quality=95, optimize=True)
        if runcount >= batchcount - 1:
            break
        runcount += 1
        print("------------------------------------------------------------")
    result['art'] = art    
    return result

    
    
    