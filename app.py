from flask import *
import time
import requests as reqs
import re
from bs4 import BeautifulSoup
#Provide the information to the webdriver about PATH and options/arguments
#browser should run headlessly
route = lambda link, x: link + f"HomeAccess/Content/Student/{x}.aspx"
session = reqs.Session()
login_data = {
    '__RequestVerificationToken': '',
    'SCKTY00328510CustomEnabled': True,
    'SCKTY00436568CustomEnabled': True,
    'Database': 10,
    'VerificationOption': 'UsernamePassword',
    'LogOnDetails.UserName': '',
    'tempUN': '',
    'tempPW': '',
    'LogOnDetails.Password': ''
}

#Create the flask app
app = Flask(__name__)
@app.route("/api", methods = ['GET'])
def main():
    start = time.time()
    result = {}
    if "user" in request.args and "pass" in request.args and "link" in request.args and '6weeks' in request.args:
        login_data["LogOnDetails.UserName"] = request.args["user"]
        username = login_data["LogOnDetails.UserName"]
        login_data["LogOnDetails.Password"] = request.args["pass"]
        password = login_data["LogOnDetails.Password"]
        gp = request.args['6weeks']
        # reccomended link format is https://url.com/arg=param 
        link = request.args["link"]
        if link[-1] != '/':
            link += '/'
        if link[:8] != "https://":
            link = "https://" + link
        success = login(username, password, link)
    else:
        error = {"login": False, 'message': "Missing one or more login credentials"}
        end = time.time()
        print(end - start)
        return error, 406, {"Content-Type": "application/json"}
    if success != -1:
        result['login'] = True
        result["Name"] = getName(link)
        temp = {}
        grades = {}
        for i in range(6): #O(n) time
            temp[f"Grading Period {i+1} Averages"] = getAverages(i+1, link)
            grades[f'Grading Period {i+1} Assignments'] = getGrades(i+1, link)
        result["Averages"] = temp
        result["Classes"] = trim(getAverages(1, link))
        result["Info"] = getStudentInfo(link)
        result['Grades'] =grades
        result['Progress Reports'] = getIPR(link)
        result['Report Cards'] = getRepCard(link)
        end = time.time()
        print(end - start)
        return json.dumps(result), 200, {"Content-Type": "application/json"}
    else:
        return json.dumps({'login': 'false', 'message': 'invalid username, password, or link'}), 406, {"Content-Type": "application/json"}

# Goal: Create an accessible webpage API to retrieve HAC grades from ALL previous 6 weeks
#Create root page for the webpage and route them to try to login      
# dont worry about how to format things, the user will never see the API
# could be published onine later seperately if it works particularly well
def linkVerif(link: str):
    test = link + "HomeAccess/Account/LogOn"
    try:
        t = session.get(test)
    except:
        return False
    login_data["__RequestVerificationToken"]  = BeautifulSoup(t.content, 'lxml').find('input', attrs={'name': '__RequestVerificationToken'})['value']
    return True

#headlessly open the HAC website and log in
def login(user: str, passkey: str, link: str) -> int:
    start = time.time()
    if user != passkey != link != None:
        if not linkVerif(link):
            return -1
        url = link + "HomeAccess/Account/LogOn"
        screen = session.get(url)
        soop = BeautifulSoup(screen.content, 'lxml')
        post_req = session.post(url, data=login_data)
        print(time.time() - start)
        return 1

#Retrieve user's classes averages from hac and format them

def getAverages(gp, link) -> dict[str, str]:
    start = time.time()
    raw = session.get(route(link, "Assignments"))
    grades = BeautifulSoup(raw.content, 'lxml')
    classes = []
    temp = []
    oClasses = {}
    for opt in grades.find('select', attrs = {'name': 'ctl00$plnMain$ddlReportCardRuns'}).find_all('option'): #O(n)
        if opt.text == gp:
            grades.find('option', attrs = {'selected': 'selected'}).attrs['selected'] = ''
            opt.attrs['selected'] = "selected"
    for i in grades.find_all('a', class_ = "sg-header-heading"):  #O(n)
        classes.append(i.text.strip())
    for j in grades.find_all('span', class_='sg-header-heading sg-right'): #O(n)
        temp.append(j.text.strip())
    end = time.time()
    return {classes[i]: temp[i] for i in range(len(temp))}
def getName(link) -> str:
    start = time.time()
    home = session.get(link + 'HomeAccess/Classes/Classwork')
    name = BeautifulSoup(home.content, 'lxml').find('li', attrs={'class': 'sg-banner-menu-element sg-menu-element-identity'}).findChild('span').text
    return name.strip()
def trim(dictionary: dict) -> list[str]:
    return list(dictionary.keys())

def getStudentInfo(link) -> dict[str]:
    start = time.time()
    page = session.get(route(link,"Registration"))
    info = BeautifulSoup(page.content, 'lxml')
    t = []
    te = []
    keys = info.find_all('label')
    for key in keys:
        t.append(key.text.strip())
    t.remove("Graduation Components")
    vals = info.find_all("span")
    for val in vals:
        te.append(val.text.strip())
    return dict(map(lambda i,j: (i, j), t, te))

class Assignment:
    def __init__(self, args) -> None:
        if len(args) == 5:
            self.rep = {
                'Category':  args[0],
                'Points': args[1],
                "Total": args[2],
                "Percent": args[3],
                "Weighted Points": args[4]
            }
        else:
            self.rep = {
                'Due Date': args[0],
                'Date Assigned': args[1],
                'Assignment Name': args[2],
                'Grade Type': args[3],
                'Grade': args[4],
                'Total Points': args[5],
                'Weight': args[6],
                'Weighted Score': args[7],
                'Weighted Total': args[8],
                "Percentage Score": f'0.000%' if float(args[8]) == 0 else f"{'%.3f',(float(args[7]) / float(args[8]))}%"       
            }
    def toDict(self) -> dict[vars]:
        return self.rep

def getGrades(gp, link) -> dict[str: dict[vars]]:
    start = time.time()
    page = session.get(route(link, "Assignments"))
    assignments = BeautifulSoup(page.content, 'lxml')
    classes = trim(getAverages(gp, link))
    table = []
    row = []
    final = {classes[i]: [] for i in range(len(classes))}
    final['Assignment'] = []
    final['Advanced Grade Stats'] = []
    work = assignments.find_all('div', attrs={'class': 'AssignmentClass'})
    for pd in work:
        if not pd.find('div', class_='sg-header'):
            return {'message': 'No information could be loaded for this student during the provided grading period'}
        t = pd.find('table', class_='sg-asp-table')
        if t:
            for tab in pd.find_all('table',  class_='sg-asp-table'):
                for r in tab.find_all('tr', class_='sg-asp-table-data-row'):
                    for attr in r.find_all('td'):
                        text = attr.text.replace("*", "").strip()
                        row.append(text)
                    row.pop(-1)
                    table.append(Assignment(row).toDict())
                    row.clear()
                if 'CourseCategories' in tab.attrs['id']:
                    final['Advanced Grade Stats'].append(table)
                elif 'CourseAssignments' in tab.attrs['id']:
                    final['Assignment'].append(table)
                table.clear()
        else:
            final['Assignment'].append([])
            final['Advanced Grade Stats'].append([])
    #create a dictionary for each row of data with keys being the values of the headers
    """ What I want the dictionary to look like
    {
        'assignments': {
            'AP Research GT A': [
                'assignment name': {
                'due date':  'date',
                'category': '...',
                'grade': 'n/100',
                'weight': 'num',
                'adjusted': 'n/100',
                '%': 'n.000%'
                },
                
            ], 
        }
    } """
    
    temp = {}
    for c in range(len(classes)):
        tt = {}
        tt['Class Average'] = getVals(getAverages(gp, link))[c]
        tt['Assignments'] = final['Assignment'][c]
        tt['Advanced Grade Stats'] = final['Advanced Grade Stats'][c]
        temp[classes[c]] = tt        
    if len(temp) == 0:
        return {'message': 'No information could be found for this student.'}
    print(f'{time.time() - start} seconds to get grades')
    return temp

def getTranscript(link) -> dict[vars]:
    start = time.time()
    page = session.get(route(link, "Transcript"))
    transcript = BeautifulSoup(page.content, 'lxml')
    semesters = transcript.find('table')
    final = {}
    temp = []
    for cell in semesters.find_all('td', class_='sg-transcript-group'):
        if not cell:
            return {'message': 'No info found'}
        for element in cell.find_all('span'):
            temp.append(element.strip())
        final[f'Grade {temp[5].text} Semester {temp[4].text}'] = [temp]
        t = []
        t.append([j.text for j in cell.find("tr", class_='sg-asp-table-header-row').find_all('td')])
        for row in cell.find_all('tr', class_='sg-asp-table-data-row'):
            t.append([i.text for i in row.find_all('td')]) #O(n^3)
        a = []
        for k in range(len(t) - 1):
            a.append({})
            for l in range(len(t[0])):
                a[k][t[0][l]] =  t[k][l] #O(n^3)
    if len(a) == 0:
        return {'message': 'No info found'}
    print(f'{time.time() - start} seconds to get transcript')
    return a

def getVals(dict):
    keys = list(dict.keys())
    vals = []
    
    for i in range(len(keys)):
        vals.append(dict[keys[i]])
    return vals

def __keyExists__(dic, key):
    try:
        x = dic[key]
        return True
    except KeyError:
        return False     

def getIPR(link) -> dict[vars]:
    start = time.time()
    page = session.get(route(link, "InterimProgress"))
    content = BeautifulSoup(page.content, 'lxml')
    c = []
    for opt in content.find('select', attrs = {'name': 'ctl00$plnMain$ddlIPRDates'}).find_all('option'):
        if __keyExists__(opt.attrs, 'selected') in [True, False]:
            opt.attrs['selected'] = "selected"
            table = content.find('table', class_='sg-asp-table')
            a = [[cell.text for cell in table.find('tr', 'sg-asp-table-header-row').find_all('td')], []]
            a.pop(1)
            for row in table.find_all('tr', 'sg-content-table-data-row'):
                a.append([cell.text for cell in row.find_all('td')]) #O(n^3)
            keys = a[0]
            a.pop(0)
            b = [{keys[i]: val[i] for i in range(len(keys))} for val in a] #O(n^3)
            c.append(b)
            del opt.attrs['selected']
    if len(a) == 0:
        return {'message': 'No info found'}
    print(f'{time.time() - start} seconds to get IPR')
    return c
    
        

def getRepCard(link) -> dict[vars]:
    start = time.time()
    page = session.get(route(link, "ReportCards"))
    content = BeautifulSoup(page.content, 'lxml')
    c = []
    for opt in content.find('select', attrs = {'name': 'ctl00$plnMain$ddlRCRuns'}).find_all('option'):
        if __keyExists__(opt.attrs, 'selected') in [True, False]:
            opt.attrs['selected'] = "selected"
            table = content.find('table', class_='sg-asp-table')
            a = [[cell.text for cell in row.find_all('td')] for row in table.find_all('tr', 'sg-content-table-data-row')]
            keys = [cell.text for cell in table.find('tr', 'sg-asp-table-header-row').find_all('td')]
            b = [{keys[i]: val[i] for i in range(len(keys))} for val in a] #O(n^3)
            c.append(b)
            del opt.attrs['selected']
    if len(a) == 0:
        return {'message': 'No info found'}
    print(f'{time.time() - start} seconds to get report cards')
    return c


if __name__ == '__main__':
    app.run()