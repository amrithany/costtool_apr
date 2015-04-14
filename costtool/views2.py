from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect,render, render_to_response
from django.db import IntegrityError
from django.template import Context, loader, RequestContext
from django.contrib.auth import authenticate, login as auth_login
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from costtool import models as m
from costtool.forms import LoginForm, PricesForm, PricesSearchForm, PriceIndicesForm, NonPerIndicesForm, WageDefaults, WageConverter,UMConverter, PriceBenefits, PriceSummary,MultipleSummary, UserForm, UserProfileForm, ProjectsForm, ProgramsForm, ProgramDescForm, ParticipantsForm, EffectForm,SettingsForm, GeographicalForm, GeographicalForm_orig, InflationForm, InflationForm_orig, IngredientsForm,IngredientsFullForm
from costtool.functions import calculations

import xlrd
import MySQLdb
import math

def add_program(request):
    project_id = request.session['project_id']
    context = RequestContext(request)

    if request.method == 'POST':
        programform = ProgramsForm(request.POST)

        if programform.is_valid():
            progname = programform.save(commit=False)
            progname.projectId = project_id
            progname.save()
            return HttpResponseRedirect('/project/programs/'+project_id+'/program_list.html')
        else:
            print programform.errors

    else:
        programform = ProgramsForm()

    return render(request,
            'project/programs/add_program.html',
            {'programform': programform,'project_id':project_id})


def indices(request):
    project_id = request.session['project_id']
    return render(request,'project/indices.html',{'project_id':project_id})

def about(request):
    if 'user' in request.session:
        del request.session['user']
    if 'password' in request.session:   
       del request.session['password']
    template = loader.get_template('/about.html')
    return HttpResponse(template.render(context))

def settings(request):
    project_id = request.session['project_id']
    return render(request, 'project/settings.html',{'project_id':project_id})

def prices(request):
    if 'user' in request.session:
       user = request.session['user']
    else:
       user = 'ccc'
    if 'password' in request.session:
       password = request.session['password']
    else:
       password = 'ccc'

    if user == 'cbcse' and password == 'apr16':
       return render(request,'prices/prices.html')
    else:
       return render(request, 'prices/message.html')

def login(request):
   context = RequestContext(request)
   if 'user' in request.session:
      del request.session['user']
   if 'password' in request.session:   
      del request.session['password']

   if request.method == 'POST':
      loginform = LoginForm(request.POST)
      if loginform.is_valid():
         login = loginform.save(commit=False)
         request.session['user'] = login.user
         request.session['password'] = login.password
         if login.user == 'cbcse' and login.password == 'apr16':
            return HttpResponseRedirect('/project/project_list.html')
         else:
            form_errors = 'Yes'
            print form_errors
   else:
      loginform = LoginForm()

   return render_to_response('login/login.html',{'loginform': loginform}, context)

def imports(request):
    return render(request,'prices/imports.html')

def full_table(request):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']
    progname = request.session['programname']                                                                                        
    
    total_cost = 0                                                                                                                
    avg_cost = ''

    try:
       sett = m.Settings.objects.get(projectId=request.session['project_id'])
       discountRateEstimates = sett.discountRateEstimates
       infEstimate = m.InflationIndices.objects.get(projectId=request.session['project_id'],yearCPI=sett.yearEstimates)
       geoEstimate = m.GeographicalIndices.objects.get(projectId=request.session['project_id'],stateIndex=sett.stateEstimates,areaIndex=sett.areaEstimates)
       
    except ObjectDoesNotExist:
       discountRateEstimates = 3.5
       infEstimate = 2011
       geoEstimate = 100

    try:
       programdesc = m.ProgramDesc.objects.get(programId = request.session['program_id'])
       numberofparticipants = programdesc.numberofparticipants
       programdescid = programdesc.id 
    except ObjectDoesNotExist:
       numberofparticipants = 1
       programdescid = 0

    try:
       ingredients = m.Ingredients.objects.filter(programId = program_id)
       for i in ingredients:
          total_cost = i.totalCost
          if numberofparticipants is not None:
             avg_cost = float(i.totalCost) / float(numberofparticipants)
             avg_cost = round(avg_cost,2)
    except ObjectDoesNotExist:
       total_cost = 0                                                                                                                
       avg_cost = ''

    if request.method == 'POST' and request.is_ajax():
       if 'id' in request.POST:
          i = m.Ingredients.objects.get(pk=request.POST.get('id'))
          i.ingredient = request.POST.get('ingredient')
          i.category = request.POST.get('category')
          i.yearQtyUsed = request.POST.get('yearQtyUsed')
          i.variableFixed = request.POST.get('variableFixed')
          i.quantityUsed = request.POST.get('quantityUsed')
          if i.quantityUsed is None:
             i.quantityUsed = 1 
          i.lifetimeAsset = request.POST.get('lifetimeAsset')
          i.interestRate = request.POST.get('interestRate')
          i.benefitRate = request.POST.get('benefitRate')
          i.percentageofUsage = request.POST.get('percentageofUsage')
          
          try:                                                                                                                             
             inf = m.InflationIndices.objects.get(projectId=request.session['project_id'],yearCPI=i.yearPrice)
             infinf = inf.indexCPI
          except ObjectDoesNotExist:
             infinf = 700
   
          try:
             geo = m.GeographicalIndices.objects.get(projectId=request.session['project_id'],stateIndex=i.statePrice,areaIndex=i.areaPrice)
             geoIndex = geo.geoIndex
          except ObjectDoesNotExist:
             geoIndex = '100'
  
          if i.totalCost is None:
             i.totalCost = 0.0
  
          if i.interestRate == '0.0' or i.interestRate == 0.0 or i.interestRate == '0':
             i.priceAdjAmortization = float(i.convertedPrice) / float(i.lifetimeAsset)
          else:
             i.priceAdjAmortization = float(i.convertedPrice) * ((float(i.interestRate)/100)*math.pow((1+(float(i.interestRate)/100)),float(i.lifetimeAsset)))/ (math.pow((1+(float(i.interestRate)/100)),float(i.lifetimeAsset))-1) 
          if i.category == 'Personnel':
             i.priceAdjBenefits = float(i.priceAdjAmortization) * (1 + float(i.benefitRate)/float(100))
          else:
             i.priceAdjBenefits = i.priceAdjAmortization
          i.priceAdjInflation = str(float(i.priceAdjBenefits) * (float(infEstimate.indexCPI) / float(infinf)))
          i.priceAdjGeographicalArea = str(float(i.priceAdjInflation) * (float(geoEstimate.geoIndex) / float(geoIndex)))
          i.priceNetPresentValue = float(i.priceAdjGeographicalArea) * math.exp((1 - int(i.yearQtyUsed)) * (discountRateEstimates/100))
          i.adjPricePerIngredient = i.priceNetPresentValue
          if i.percentageofUsage == 100:
             i.costPerIngredient = i.adjPricePerIngredient * float(i.quantityUsed)
          else:
             i.costPerIngredient = i.adjPricePerIngredient * float(i.quantityUsed) * (float(i.percentageofUsage)/100)
          try:
             partperyear = m.ParticipantsPerYear.objects.get(programdescId_id=programdescid, yearnumber=i.yearQtyUsed)
             i.costPerParticipant = float(i.costPerIngredient) / float(partperyear.noofparticipants)
             i.save(update_fields=['ingredient','category','yearQtyUsed','variableFixed','quantityUsed','lifetimeAsset','interestRate','benefitRate', 'percentageofUsage','priceAdjAmortization','priceAdjBenefits' ,'priceAdjInflation','priceAdjGeographicalArea','priceNetPresentValue', 'adjPricePerIngredient','costPerIngredient', 'costPerParticipant']) 
          except ObjectDoesNotExist:
             i.costPerParticipant = ''
             i.save(update_fields=['ingredient','category','yearQtyUsed','variableFixed','quantityUsed','lifetimeAsset','interestRate','benefitRate', 'percentageofUsage','priceAdjAmortization','priceAdjBenefits' ,'priceAdjInflation','priceAdjGeographicalArea','priceNetPresentValue', 'adjPricePerIngredient','costPerIngredient'])
          total_cost = 0
          ing = m.Ingredients.objects.filter(programId = program_id)
          for i in ing:
              total_cost = total_cost + i.costPerIngredient
          for i in ing:
              i.totalCost = total_cost
              i.percentageCost = i.costPerIngredient * 100 /i.totalCost
              if numberofparticipants is not None:
                 i.averageCost = float(i.totalCost) / float(numberofparticipants)
                 avg_cost = round(i.averageCost,2)
                 i.save(update_fields=['totalCost','averageCost','percentageCost'])   
              else:
                 i.save(update_fields=['totalCost','percentageCost'])   
       else:
          print 'no id given'
    return render_to_response('project/programs/costs/full_table.html',{'ingredients':ingredients,'project_id':project_id, 'program_id':program_id,'total_cost':round(total_cost,2),'avg_cost':avg_cost,'projectname':projectname, 'programname':progname, 'discountRateEstimates':discountRateEstimates, 'infEstimate':infEstimate,'geoEstimate':geoEstimate, 'geoArea':'' },context)

def tabbedlayout(request,project_id,program_id):
    project = m.Projects.objects.get(pk=project_id)
    program = m.Programs.objects.get(pk=program_id)
    request.session['program_id'] = program_id
    request.session['projectname'] = project.projectname
    request.session['programname'] = program.progname

    effectform = EffectForm()
    total_cost = 0                                                                                                                                    
    avg_cost = ''
    IngFormSet = modelformset_factory(m.Ingredients,extra=20)
    ingform = IngFormSet(queryset = m.Ingredients.objects.filter(programId = program_id),prefix="ingform")
    try:
        programdesc = m.ProgramDesc.objects.get(programId=program_id)
        form1 = ProgramDescForm(request.POST, instance=programdesc)
        numberofparticipants = programdesc.numberofparticipants
        progid = programdesc.id
        objectexists = True
    except ObjectDoesNotExist:
        form1 = ProgramDescForm(request.POST)
        numberofparticipants = 1
        progid = 0
        objectexists = False

    try:
        ing = m.Ingredients.objects.filter(programId = program_id)
        for i in ing:
           total_cost = i.totalCost
           total_cost = round(total_cost, 2)
           if numberofparticipants is not None:
               avg_cost = float(i.totalCost) / float(numberofparticipants)
               avg_cost = round(avg_cost, 2)
    except ObjectDoesNotExist:
       total_cost = 0                                                                                                                                    
       avg_cost = ''

    PartFormSet = inlineformset_factory(m.ProgramDesc,m.ParticipantsPerYear,form=ParticipantsForm,extra=10)
    if objectexists:
        try:
            partform = PartFormSet(request.POST,request.FILES, instance=programdesc,prefix="partform" )
            partobjexists = True
        except ObjectDoesNotExist:
            partform = PartFormSet(request.POST, request.FILES,prefix="partform")
            partobjexists = False
    else:
        partform = PartFormSet(request.POST, request.FILES,prefix="partform")
        partobjexists = False

    if partobjexists:
        partform = PartFormSet( instance=programdesc,prefix="partform")
    else:
        partform = PartFormSet(prefix="partform")   
 
    if request.method == 'POST':
        if 'submit1' in request.POST:
            if form1.is_valid():
               id = form1.save(commit=False)
               id.numberofyears = 1
               id.programId = program
               id.save()
               programdesc = m.ProgramDesc.objects.get(pk=id.id)
               partform = PartFormSet(request.POST,request.FILES, instance=programdesc,prefix="partform" )
               if partform.is_valid():
                  partform.save()
                  m.ParticipantsPerYear.objects.filter(noofparticipants__isnull=True).delete() 
                  programdesc.numberofyears=m.ParticipantsPerYear.objects.filter(programdescId=id.id).count()
                  programdesc.save()
                  request.session['programdescId'] = programdesc.id
                  if project.typeanalysis == 'Cost Analysis':
                     return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/'+ program_id +'/tabbedview.html?activeform=costform')
                  else:
                     return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/'+ program_id +'/tabbedview.html?activeform=effform')
               else:
                  print partform.errors
                  return render (request,'project/programs/effect/tabbedview.html',{'total_cost':total_cost,'avg_cost':avg_cost,'active':'form1','project':project,'program':program,'frm1':form1,'partform':partform, 'frm3':ingform,'partform.errors':partform.errors,'frm2':effectform})
            else:
               print form1.errors
               return render (request,'project/programs/effect/tabbedview.html',{'total_cost':total_cost,'avg_cost':avg_cost,'active':'form1','project':project,'program':program,'frm1':form1,'partform':partform, 'frm3':ingform,'form1.errors':form1.errors,'frm2':effectform})
    else:
       if objectexists:
          form1 = ProgramDescForm(instance=programdesc)
       else:
          form1 = ProgramDescForm()
        
       if partobjexists:
          partform = PartFormSet( instance=programdesc, prefix="partform",initial=[{'yearnumber': "%d" % (i+1)} for i in range(programdesc.numberofyears,programdesc.numberofyears+10)])
       else:
          partform = PartFormSet(prefix="partform",initial=[{'yearnumber': "%d" % (i+1)} for i in range(10)])

    try:
       effect = m.Effectiveness.objects.get(programId=program_id)
       effectform = EffectForm(request.POST, instance=effect)
       effobjexists = True
    except ObjectDoesNotExist:
       effectform = EffectForm(request.POST)
       effobjexists = False
                
    if request.method == 'POST':
       if 'submit2' in request.POST:
          if effectform.is_valid():
             sourceeffectdata = effectform.save(commit=False)
             sourceeffectdata.programId = program
             sourceeffectdata.save()
             return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/'+ program_id +'/tabbedview.html?activeform=costform')
          else:
             print effectform.errors
             return render (request,'project/programs/effect/tabbedview.html',{'total_cost':total_cost,'avg_cost':avg_cost,'active':'effform','project':project,'program':program,'frm1':form1,'partform':partform, 'frm2':effectform, 'frm3':ingform,'effectform.errors':effectform.errors})
    else:
       if effobjexists:                                                                                                            
          effectform = EffectForm(instance=effect)
       else:
          effectform = EffectForm()   

    IngFormSet = modelformset_factory(m.Ingredients,extra=20)

    if request.method == 'POST':
       if 'editIng' in request.POST:
          ingform = IngFormSet(request.POST,request.FILES,prefix="ingform")
          if ingform.is_valid():
             f = ingform.save(commit=False)
             for ing in f:
                if ing.percentageofUsage is None:
                   ing.percentageofUsage = 100     
                if ing.percentageofUsage == 100:
                   ing.costPerIngredient = ing.adjPricePerIngredient * ing.quantityUsed
                else:
                   ing.costPerIngredient = ing.adjPricePerIngredient * ing.quantityUsed * ing.percentageofUsage / 100 
                try:
                   partperyear = m.ParticipantsPerYear.objects.get(programdescId_id=progid, yearnumber=ing.yearQtyUsed)
                   ing.costPerParticipant = float(ing.costPerIngredient) / float(partperyear.noofparticipants)
                   ing.save(update_fields=['ingredient', 'quantityUsed','variableFixed','costPerIngredient','costPerParticipant']) 
                except ObjectDoesNotExist:
                   ing.costPerParticipant = ''
                   ing.save(update_fields=['ingredient', 'quantityUsed','variableFixed','costPerIngredient'])
          
             ing1 = m.Ingredients.objects.filter(programId = program_id)
             total_cost = 0
             for i in ing1:
                total_cost = total_cost + i.costPerIngredient
             for i in ing1:
                i.totalCost = total_cost
                total_cost = round(total_cost,2)
                i.percentageCost = float(i.costPerIngredient) * (100 / float(i.totalCost))
                if numberofparticipants is not None:
                   i.averageCost = float(i.totalCost) / float(numberofparticipants)
                   avg_cost = i.averageCost
                   avg_cost = round(avg_cost,2)
                   i.save(update_fields=['totalCost','averageCost','percentageCost'])
                else: 
                   avg_cost = ''
                   i.save(update_fields=['totalCost','percentageCost'])
             return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/'+ program_id +'/tabbedview.html?activeform=costform')
          else:
             print ingform.errors
             return render (request,'project/programs/effect/tabbedview.html',{'total_cost':total_cost,'avg_cost':avg_cost,'active':'costform','project':project,'program':program,'frm1':form1,'partform':partform, 'frm3':ingform,'ingform.errors':ingform.errors,'frm2':effectform})
    else:
       ing = m.Ingredients.objects.filter(programId = program_id)
       for i in ing:
          total_cost = round(i.totalCost,2)
          if numberofparticipants is not None:  
             avg_cost = round(float(i.totalCost) / float(numberofparticipants),2) 
       ingform = IngFormSet(queryset = ing,prefix="ingform")
       for form in ingform:
          form.fields['newMeasure'].widget.attrs['readonly'] = True 
          form.fields['yearQtyUsed'].widget.attrs['readonly'] = True
          form.fields['totalCost'].widget.attrs['readonly'] = True 
          form.fields['adjPricePerIngredient'].widget.attrs['readonly'] = True
          form.fields['costPerIngredient'].widget.attrs['readonly'] = True
          form.fields['percentageCost'].widget.attrs['readonly'] = True
          form.fields['costPerParticipant'].widget.attrs['readonly'] = True
    return render (request,'project/programs/effect/tabbedview.html',{'total_cost':total_cost,'avg_cost':avg_cost,'project':project,'program':program,'frm1':form1,'partform':partform, 'frm3':ingform,'frm2':effectform})

def del_ingredient(request, ing_id):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    try:
       programdesc = m.ProgramDesc.objects.get(programId = program_id)
       numberofparticipants = programdesc.numberofparticipants
    except ObjectDoesNotExist:
       numberofparticipants = 1

    m.Ingredients.objects.get(pk=ing_id).delete()
    total_cost = 0
    ing = m.Ingredients.objects.filter(programId = program_id)
    for i in ing:
        total_cost = total_cost + i.costPerIngredient
    for i in ing:
        i.totalCost = total_cost
        i.percentageCost = i.costPerIngredient * 100 / i.totalCost
        if numberofparticipants is not None:
           i.averageCost = float(i.totalCost) / float(numberofparticipants)
           avg_cost = i.averageCost
           i.save(update_fields=['totalCost','averageCost','percentageCost'])
        else:   
           i.save(update_fields=['totalCost','percentageCost'])
    return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/'+ program_id +'/tabbedview.html?activeform=costform')

def dupl_ingredient(request, ing_id):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    try:
       programdesc = m.ProgramDesc.objects.get(programId = program_id)
       numberofparticipants = programdesc.numberofparticipants
    except ObjectDoesNotExist:
       numberofparticipants = 1
   
    ingredient = m.Ingredients.objects.get(pk=ing_id)
    if ingredient.yearQtyUsed is None:
       ingredient.yearQtyUsed = 1

    m.Ingredients.objects.create(SourceBenefitData = ingredient.SourceBenefitData, category = ingredient.category, ingredient = ingredient.ingredient, edLevel = ingredient.edLevel, sector = ingredient.sector, unitMeasurePrice = ingredient.unitMeasurePrice, price =  ingredient.price, sourcePriceData = ingredient.sourcePriceData, urlPrice = ingredient.urlPrice, newMeasure = ingredient.newMeasure, convertedPrice = ingredient.convertedPrice, yearPrice = ingredient.yearPrice, statePrice = ingredient.statePrice, areaPrice = ingredient.areaPrice, programId = ingredient.programId, lifetimeAsset = ingredient.lifetimeAsset, interestRate = ingredient.interestRate, benefitRate = ingredient.benefitRate, indexCPI = ingredient.indexCPI, geoIndex = ingredient.geoIndex, quantityUsed = ingredient.quantityUsed, variableFixed = ingredient.variableFixed, yearQtyUsed = ingredient.yearQtyUsed, priceAdjAmortization = ingredient.priceAdjAmortization, percentageofUsage = ingredient.percentageofUsage, adjPricePerIngredient = ingredient.adjPricePerIngredient, priceAdjInflation = ingredient.priceAdjInflation, priceAdjBenefits = ingredient.priceAdjBenefits,priceAdjGeographicalArea = ingredient.priceAdjGeographicalArea, priceNetPresentValue = ingredient.priceNetPresentValue, costPerIngredient = ingredient.costPerIngredient, costPerParticipant = ingredient.costPerParticipant )

    total_cost = 0
    ing = m.Ingredients.objects.filter(programId = program_id)
    for i in ing:
        total_cost = total_cost + i.costPerIngredient
    for i in ing:
        i.totalCost = total_cost
        i.percentageCost = i.costPerIngredient * 100 / i.totalCost
        if numberofparticipants is not None:
           i.averageCost = float(i.totalCost) / float(numberofparticipants)
           avg_cost = i.averageCost
           i.save(update_fields=['totalCost','averageCost','percentageCost'])
        else:   
           i.save(update_fields=['totalCost','percentageCost'])
    return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/'+ program_id +'/tabbedview.html?activeform=costform')

def search_costs(request):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname'] 
    progname = request.session['programname']

    try:
       sett = m.Settings.objects.get(projectId = project_id)
       choicesEdn = ''
       choicesSec = ''
       if 'Select' in sett.limitEdn:
          choicesEdn = 'All,General,Grades PK,Grades K-6,Grades 6-8,Grades 9-12,Grades K-12,PostSecondary'
       else:
          if 'General' in sett.limitEdn:
             choicesEdn = choicesEdn + ',General'
          if 'Grades PK' in sett.limitEdn:
             choicesEdn = choicesEdn + ',Grades PK'
          if 'Grades K-6' in sett.limitEdn:
             choicesEdn = choicesEdn + ',Grades K-6'
          if 'Grades 6-8' in sett.limitEdn:
             choicesEdn = choicesEdn + ',Grades 6-8'
          if 'Grades 9-12' in sett.limitEdn:
             choicesEdn = choicesEdn + ',Grades 9-12'
          if 'Grades K-12' in sett.limitEdn:
             choicesEdn = choicesEdn + ',Grades K-12'
          if 'PostSecondary' in sett.limitEdn:
             choicesEdn = choicesEdn + ',PostSecondary'

       if 'Select' in sett.limitSector:
          choicesSec = 'All,Any,Private,Public'
       else:
          if 'Any' in sett.limitSector:
             choicesSec = choicesSec + ',Any'
          if 'Private' in sett.limitSector:
             choicesSec = choicesSec + ',Private'
          if 'Public' in sett.limitSector:
             choicesSec = choicesSec + ',Public'

    except ObjectDoesNotExist:
       choicesEdn = 'All,General,Grades PK,Grades K-6,Grades 6-8,Grades 9-12,Grades K-12,PostSecondary'
       choicesSec = 'All,Any,Private,Public'
  
    if 'hrsCalendarYr' in request.session:
        del request.session['hrsCalendarYr']

    if 'hrsAcademicYr' in request.session:
        del request.session['hrsAcademicYr']

    if 'hrsHigherEdn' in request.session:
        del request.session['hrsHigherEdn']

    if 'price' in request.session:
        del request.session['price']

    if 'measure' in request.session:
        del request.session['measure']

    if 'price_id' in request.session:
        del request.session['price_id']

    if 'Rate' in request.session:
        del request.session['Rate']

    if 'benefit_id' in request.session:
        del request.session['benefit_id']

    if 'search_cat' in request.session:
       del request.session['search_cat']

    if 'search_edLevel' in request.session:
       del request.session['search_edLevel']

    if 'search_sector' in request.session:
       del request.session['search_sector']
    
    if 'search_ingredient' in request.session:
       del request.session['search_ingredient']

    if 'lifetimeAsset' in request.session:
       del request.session['lifetimeAsset']

    if 'interestRate' in request.session:
       del request.session['interestRate']

    if request.method == 'POST':
        costform = PricesSearchForm(data=request.POST)
        if costform.is_valid():
            priceProvider = costform.save(commit=False)
            return HttpResponseRedirect('/project/programs/costs/price_search_results.html')
        else:
            print costform.errors
            return HttpResponse(costform.errors)
    else:
       costform = PricesSearchForm()
    return render_to_response('project/programs/costs/search_costs.html',{'costform':costform,'choicesEdn':choicesEdn,'choicesSec':choicesSec,'project_id':project_id, 'program_id':program_id,'projectname':projectname, 'programname':progname},context)

def price_search(request):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']
    progname = request.session['programname']       

    if 'new_price' in request.session:
        del request.session['new_price']

    if 'new_measure' in request.session:
        del request.session['new_measure']

    try:
       sett = m.Settings.objects.get(projectId = project_id)
       if 'CBCSE' in sett.selectDatabase and 'My' in sett.selectDatabase:
          prices = m.Prices.objects.all()
       elif 'CBCSE' in sett.selectDatabase:
          prices = m.Prices.objects.filter(priceProvider = 'CBCSE')
       elif 'My' in sett.selectDatabase:
          prices = m.Prices.objects.filter(priceProvider = 'User')

       #if 'recent' in sett.limitYear:
          #latest = m.Prices.objects.all().latest('yearPrice')
          #prices = prices.latest('yearPrice')
    except ObjectDoesNotExist:
       prices = m.Prices.objects.all()
 
    if 'category' in request.GET or 'edlevel' in request.GET or 'sector' in request.GET or 'ingredient' in request.GET:
       cat = request.GET['category']
       request.session['search_cat'] = cat
       edLevel = request.GET['edLevel']
       request.session['search_edLevel'] = edLevel 
       sector = request.GET['sector']
       request.session['search_sector'] = sector
       ingredient = request.GET['ingredient']
       request.session['search_ingredient'] = ingredient
       kwargs = { }
       if cat:
          if cat != 'All': 
             kwargs['category'] = cat
             
       prices = prices.filter(**kwargs)
       if edLevel:
          if edLevel == 'All':
             edLevellist = ['','General','Grades PK','Grades K-6','Grades 6-8','Grades 9-12','Grades K-12','PostSecondary'] 
          elif edLevel == 'Grades K-12': 
             edLevellist = ['Grades K-6','Grades 9-12', 'Grades 6-8','Grades K-12']
             prices = prices.filter(edLevel__in=edLevellist)
          else:
             prices = prices.filter(edLevel = edLevel)
       if sector:
          if sector == 'Any' or sector == 'All':
             sectorList = ['','Any','Public','Private']
             prices = prices.filter(sector__in=sectorList)
          else:
             prices = prices.filter(sector = sector)
       if ingredient:
          prices = prices.filter(ingredient__icontains = ingredient)
       #if 'recent' in sett.limitYear:
          #latestprice = m.Prices.objects.filter(ingredient__in = prices).latest('yearPrice')
          #prices  = prices.filter(yearPrice = latestprice.yearPrice)

       pcount = prices.count()
       template = loader.get_template('project/programs/costs/price_search_results.html')
       context = Context({'projectname':projectname, 'programname':progname,'prices' : prices, 'pcount':pcount, 'cat': cat, 'edLevel':edLevel, 'sector':sector, 'ingredient':ingredient, 'project_id':project_id, 'program_id':program_id})
       return HttpResponse(template.render(context))
    else:
        return HttpResponse('Please enter some criteria to do a search')

def decideCat(request,price_id):
    price = m.Prices.objects.get(pk=price_id)

    if price.category == 'Personnel':
       return HttpResponseRedirect('/project/programs/costs/'+ price_id +'/price_indices.html')
    else:
       return HttpResponseRedirect('/project/programs/costs/'+ price_id +'/nonper_indices.html')

    
def price_indices(request,price_id):
    price = m.Prices.objects.get(pk=price_id)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']
    progname = request.session['programname'] 

    cat =  request.session['search_cat']
    edLevel =  request.session['search_edLevel']
    sector =  request.session['search_sector']
    ingredient = request.session['search_ingredient']

    if 'new_price' in request.session:
       new_price = float(request.session['new_price'])
    else:
       new_price = price.price
       request.session['new_price'] = price.price

    if 'new_measure' in request.session:
       new_measure = request.session['new_measure']
    else:
       new_measure = price.unitMeasurePrice
       request.session['new_measure'] = price.unitMeasurePrice
 
    request.session['price_id'] = price_id
    request.session['price'] = price.price
    request.session['measure'] = price.unitMeasurePrice
    template = loader.get_template('project/programs/costs/price_indices.html')
    context = Context({
        'price' : price,
        'new_price' : new_price,
        'new_measure' : new_measure,
        'cat' : cat, 'edLevel':  edLevel, 'sector': sector,'ingredient' : ingredient, 
        'project_id':project_id, 'program_id':program_id, 'projectname':projectname, 'programname':progname 
    })
    return HttpResponse(template.render(context))

def nonper_indices(request,price_id):
    context = RequestContext(request)
    price = m.Prices.objects.get(pk=price_id)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']
    progname = request.session['programname'] 

    cat =  request.session['search_cat']
    edLevel =  request.session['search_edLevel']
    sector =  request.session['search_sector']
    ingredient = request.session['search_ingredient']

    if 'new_price' in request.session:
       new_price = request.session['new_price']
    else:
       new_price = price.price
       request.session['new_price'] = price.price

    if 'new_measure' in request.session:
       new_measure = request.session['new_measure']
    else:
       new_measure = price.unitMeasurePrice
       request.session['new_measure'] = price.unitMeasurePrice

    request.session['price_id'] = price_id
    request.session['price'] = price.price
    request.session['measure'] = price.unitMeasurePrice

    if request.method == 'POST':
        form = NonPerIndicesForm(request.POST)
        if form.is_valid():
            lifetimeAsset = form.save(commit=False)
            request.session['lifetimeAsset'] = lifetimeAsset.lifetimeAsset
            request.session['interestRate'] = lifetimeAsset.interestRate
            return HttpResponseRedirect('/project/programs/costs/nonper_summary.html')
        else:
            print form.errors
            return render_to_response('project/programs/costs/nonper_indices.html',{'form':form, 'price':price, 'new_price' : new_price, 'new_measure' : new_measure, 'cat' : cat, 'edLevel':  edLevel, 'sector': sector,'ingredient' : ingredient,'project_id':project_id, 'program_id':program_id,'form.errors':form.errors,'projectname':projectname, 'programname':progname},context)
    else:
        form = NonPerIndicesForm()

    return render_to_response('project/programs/costs/nonper_indices.html',{'form':form, 'price':price, 'new_price' : new_price, 'new_measure' : new_measure, 'cat' : cat, 'edLevel':  edLevel, 'sector': sector,'ingredient' : ingredient,'project_id':project_id, 'program_id':program_id, 'projectname':projectname, 'programname':progname},context)

def um_converter(request):
    context = RequestContext(request)
    price_id = request.session['price_id']

    if 'price' in request.session:
       price = float(request.session['price'])
    else:
       price = 0.0
       request.session['price'] = 0.0

    if 'measure' in request.session:
       measure = request.session['measure']
    else:
       measure = ''
       request.session['measure'] = ''

    if 'new_price' in request.session:
        new_price = request.session['new_price']
    else: 
        new_price = price
        request.session['new_price'] = price

    if 'new_measure' in request.session:
        new_measure = request.session['new_measure']
    else: 
        new_measure = measure
        request.session['new_measure'] = measure
    mylist = ['Sq. Inch', 'Sq. Foot','Sq. Yard','Acre','Sq. Mile','Sq. Meter','Sq. Kilometer','Hectare']
    listVol=['Ounces','Cups','Pints','Quarts','Gallons','Liters']
    listLen=['Inches','Feet','Yards','Miles','Millimeter','Centimeter','Kilometer']
    listTime=['Hour', 'Day', 'Week', 'Minutes','Hours','Days','Weeks','Years']
    allList = ['Sq. Inch', 'Sq. Foot','Sq. Yard','Acre','Sq. Mile','Sq. Meter','Sq. Kilometer','Hectare','Ounces','Cups','Pints','Quarts','Gallons','Liters','Inches','Feet','Yards','Miles','Millimeter','Centimeter','Kilometer','Minutes','Hours','Days','Weeks','Years']
    measureType = 'mylist'

    if measure == 'Other':
       measureType = 'allList'
    elif measure in mylist:
       measureType = 'mylist'
    elif measure in listVol:
       measureType = 'listVol'
    elif measure in listLen:
       measureType = 'listLen'
    elif measure in listTime:
       measureType = 'listTime'

    if request.method == 'POST':
        if 'compute' in request.POST:
            form = UMConverter(data=request.POST)
            if form.is_valid():
                newMeasure = form.save(commit=False)
                if measureType == 'mylist':
                    if measure == 'Sq. Inch':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 0.006
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 0.0007
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 0.000000159
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.000000000249
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 0.0006
                        if newMeasure.newMeasure == 'Sq. Kilometer':
                            newMeasure.convertedPrice = price * 0.000000000645
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 0.0000000645

                    if measure == 'Sq. Foot' or measure == 'Sq. Ft.':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 144
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 0.111
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 0.0000229
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.00000003587
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 0.092
                        if newMeasure.newMeasure == 'Sq. Kilometer':
			    newMeasure.convertedPrice = price * 0.0000000929
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 0.00000929

                    if measure == 'Sq. Yard':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 1296
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 9
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 0.0002
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.000000322
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 0.83
                        if newMeasure.newMeasure == 'Sq. Kilometer':
                            newMeasure.convertedPrice = price * 0.000000836
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 0.0000836

                    if measure == 'Acre':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 0.00000627
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 4840
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 43560
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.0015
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 4046.86
                        if newMeasure.newMeasure == 'Sq. Kilometer':
                            newMeasure.convertedPrice = price * 0.00404
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 0.404

                    if measure == 'Sq. Mile':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 0.000000004014
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 0.000003098
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 0.000000278
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 640
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 0.00000259
                        if newMeasure.newMeasure == 'Sq. Kilometer':
                            newMeasure.convertedPrice = price * 2.5899
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 258.999

                    if measure == 'Sq. Meter':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 1550
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 1.19
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 10.76
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 0.00024
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.000000386
                        if newMeasure.newMeasure == 'Sq. Kilometer':
                            newMeasure.convertedPrice = price * 0.000001
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 0.0001

                    if measure == 'Sq. Kilometer':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 0.000000001550
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 0.000001196
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 0.0000001076
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 247.105
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.386
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 0.000001
                        if newMeasure.newMeasure == 'Hectare':
                            newMeasure.convertedPrice = price * 100

                    if measure == 'Hectare':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasure == 'Sq. Inch':
                            newMeasure.convertedPrice = price * 0.0000001550
                        if newMeasure.newMeasure == 'Sq. Yard':
                            newMeasure.convertedPrice = price * 11959.9
                        if newMeasure.newMeasure == 'Sq. Foot':
                            newMeasure.convertedPrice = price * 107639
                        if newMeasure.newMeasure == 'Acre':
                            newMeasure.convertedPrice = price * 2.471
                        if newMeasure.newMeasure == 'Sq. Mile':
                            newMeasure.convertedPrice = price * 0.00386
                        if newMeasure.newMeasure == 'Sq. Meter':
                            newMeasure.convertedPrice = price * 10000
                        if newMeasure.newMeasure == 'Sq. Kilometer':
                            newMeasure.convertedPrice = price * 0.01

                    request.session['new_measure'] = newMeasure.newMeasure
                    new_measure = newMeasure.newMeasure
                if measureType == 'listVol':
                    if measure == 'Ounces':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureVol == 'Cups':
                            newMeasure.convertedPrice = price * 0.125
                        if newMeasure.newMeasureVol == 'Pints':
                            newMeasure.convertedPrice = price * 0.0625
                        if newMeasure.newMeasureVol == 'Quarts':
                            newMeasure.convertedPrice = price * 0.03125
                        if newMeasure.newMeasureVol == 'Gallons':
                            newMeasure.convertedPrice = price * 0.0078
                        if newMeasure.newMeasureVol == 'Liters':
                            newMeasure.convertedPrice = price * 0.029

                    if measure == 'Cups':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureVol == 'Ounces':
                            newMeasure.convertedPrice = price * 8
                        if newMeasure.newMeasureVol == 'Pints':
                            newMeasure.convertedPrice = price * 0.5
                        if newMeasure.newMeasureVol == 'Quarts':
                            newMeasure.convertedPrice = price * 0.25
                        if newMeasure.newMeasureVol == 'Gallons':
                            newMeasure.convertedPrice = price * 0.0625
                        if newMeasure.newMeasureVol == 'Liters':
                            newMeasure.convertedPrice = price * 0.236

                    if measure == 'Pints':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureVol == 'Cups':
                            newMeasure.convertedPrice = price * 2
                        if newMeasure.newMeasureVol == 'Ounces':
                            newMeasure.convertedPrice = price * 16
                        if newMeasure.newMeasureVol == 'Quarts':
                            newMeasure.convertedPrice = price * 0.5
                        if newMeasure.newMeasureVol == 'Gallons':
                            newMeasure.convertedPrice = price * 0.125
                        if newMeasure.newMeasureVol == 'Liters':
                            newMeasure.convertedPrice = price * 0.473

                    if measure == 'Quarts':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureVol == 'Cups':
                            newMeasure.convertedPrice = price * 4
                        if newMeasure.newMeasureVol == 'Pints':
                            newMeasure.convertedPrice = price * 2
                        if newMeasure.newMeasureVol == 'Ounces':
                            newMeasure.convertedPrice = price * 32
                        if newMeasure.newMeasureVol == 'Gallons':
                            newMeasure.convertedPrice = price * 0.25
                        if newMeasure.newMeasureVol == 'Liters':
                            newMeasure.convertedPrice = price * 0.946

                    if measure == 'Gallons':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureVol == 'Cups':
                            newMeasure.convertedPrice = price * 16
                        if newMeasure.newMeasureVol == 'Pints':
                            newMeasure.convertedPrice = price * 8
                        if newMeasure.newMeasureVol == 'Quarts':
                            newMeasure.convertedPrice = price * 4
                        if newMeasure.newMeasureVol == 'Ounces':
                            newMeasure.convertedPrice = price * 128
                        if newMeasure.newMeasureVol == 'Liters':
                            newMeasure.convertedPrice = price * 3.785

                    if measure == 'Liters':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureVol == 'Cups':
                            newMeasure.convertedPrice = price * 4.22
                        if newMeasure.newMeasureVol == 'Pints':
                            newMeasure.convertedPrice = price * 2.11
                        if newMeasure.newMeasureVol == 'Quarts':
                            newMeasure.convertedPrice = price * 1.05
                        if newMeasure.newMeasureVol == 'Gallons':
                            newMeasure.convertedPrice = price * 0.264
                        if newMeasure.newMeasureVol == 'Ounces':
                            newMeasure.convertedPrice = price * 33.81

                    request.session['new_measure'] = newMeasure.newMeasureVol
                    new_measure = newMeasure.newMeasureVol

                if measureType == 'listLen':
                    if measure == 'Inches':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Feet':
                            newMeasure.convertedPrice = price * 0.083
                        if newMeasure.newMeasureLen == 'Yards':
                            newMeasure.convertedPrice = price * 0.027
                        if newMeasure.newMeasureLen == 'Miles':
                            newMeasure.convertedPrice = price * 1.578
                        if newMeasure.newMeasureLen == 'Millimeter':
                            newMeasure.convertedPrice = price * 25.4
                        if newMeasure.newMeasureLen == 'Centimeter':
                            newMeasure.convertedPrice = price * 2.54
                        if newMeasure.newMeasureLen == 'Kilometer':
                            newMeasure.convertedPrice = price * 0.0000254

                    if measure == 'Feet':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Inches':
                            newMeasure.convertedPrice = price * 12
                        if newMeasure.newMeasureLen == 'Yards':
                            newMeasure.convertedPrice = price * 0.3333
                        if newMeasure.newMeasureLen == 'Miles':
                            newMeasure.convertedPrice = price * 0.00018
                        if newMeasure.newMeasureLen == 'Millimeter':
                            newMeasure.convertedPrice = price * 304.8
                        if newMeasure.newMeasureLen == 'Centimeter':
                            newMeasure.convertedPrice = price * 30.48
                        if newMeasure.newMeasureLen == 'Kilometer':
                            newMeasure.convertedPrice = price * 0.000304

                    if measure == 'Yards':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Inches':
                            newMeasure.convertedPrice = price * 36
                        if newMeasure.newMeasureLen == 'Feet':
                            newMeasure.convertedPrice = price * 3
                        if newMeasure.newMeasureLen == 'Miles':
                            newMeasure.convertedPrice = price * 0.00056
                        if newMeasure.newMeasureLen == 'Millimeter':
                            newMeasure.convertedPrice = price * 914.4
                        if newMeasure.newMeasureLen == 'Centimeter':
                            newMeasure.convertedPrice = price * 91.44
                        if newMeasure.newMeasureLen == 'Kilometer':
                            newMeasure.convertedPrice = price * 0.0009144

                    if measure == 'Miles':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Inches':
                            newMeasure.convertedPrice = price * 63360
                        if newMeasure.newMeasureLen == 'Feet':
                            newMeasure.convertedPrice = price * 5280
                        if newMeasure.newMeasureLen == 'Yards':
                            newMeasure.convertedPrice = price * 1760
                        if newMeasure.newMeasureLen == 'Millimeter':
                            newMeasure.convertedPrice = price * 0.00000160934
                        if newMeasure.newMeasureLen == 'Centimeter':
                            newMeasure.convertedPrice = price * 160934
                        if newMeasure.newMeasureLen == 'Kilometer':
                            newMeasure.convertedPrice = price * 1.609

                    if measure == 'Millimeter':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Inches':
                            newMeasure.convertedPrice = price * 0.039
                        if newMeasure.newMeasureLen == 'Feet':
                            newMeasure.convertedPrice = price * 0.00328
                        if newMeasure.newMeasureLen == 'Yards':
                            newMeasure.convertedPrice = price * 0.00109
                        if newMeasure.newMeasureLen == 'Miles':
                            newMeasure.convertedPrice = price * 0.000000621
                        if newMeasure.newMeasureLen == 'Centimeter':
                            newMeasure.convertedPrice = price * 0.1
                        if newMeasure.newMeasureLen == 'Kilometer':
                            newMeasure.convertedPrice = price * 0.000001

                    if measure == 'Centimeter':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Inches':
                            newMeasure.convertedPrice = price * 0.393
                        if newMeasure.newMeasureLen == 'Feet':
                            newMeasure.convertedPrice = price * 0.0328
                        if newMeasure.newMeasureLen == 'Yards':
                            newMeasure.convertedPrice = price * 0.0109
                        if newMeasure.newMeasureLen == 'Miles':
                            newMeasure.convertedPrice = price * 0.00000621
                        if newMeasure.newMeasureLen == 'Millimeter':
                            newMeasure.convertedPrice = price * 10
                        if newMeasure.newMeasureLen == 'Kilometer':
                            newMeasure.convertedPrice = price * 0.00001

                    if measure == 'Kilometer':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureLen == 'Inches':
                            newMeasure.convertedPrice = price * 39370.1
                        if newMeasure.newMeasureLen == 'Feet':
                            newMeasure.convertedPrice = price * 3280.84
                        if newMeasure.newMeasureLen == 'Yards':
                            newMeasure.convertedPrice = price * 1093.61
                        if newMeasure.newMeasureLen == 'Miles':
                            newMeasure.convertedPrice = price * 0.621
                        if newMeasure.newMeasureLen == 'Centimeter':
                            newMeasure.convertedPrice = price * 100000
                        if newMeasure.newMeasureLen == 'Millimeter':
                            newMeasure.convertedPrice = price * 0.000001

                    request.session['new_measure'] = newMeasure.newMeasureLen
                    new_measure = newMeasure.newMeasureLen

                if measureType == 'listTime':
                    if measure == 'Minutes':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureTime == 'Hours' or newMeasure.newMeasureTime == 'Hour':
                            newMeasure.convertedPrice = price * 0.016
                        if newMeasure.newMeasureTime == 'Days' or  newMeasure.newMeasureTime == 'Day':
                            newMeasure.convertedPrice = price * 0.00069
                        if newMeasure.newMeasureTime == 'Weeks' or  newMeasure.newMeasureTime == 'Week':
                            newMeasure.convertedPrice = price * 0.0000992
                        if newMeasure.newMeasureTime == 'Years':
                            newMeasure.convertedPrice = price * 0.0000019

                    if measure == 'Hours' or measure == 'Hour':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureTime == 'Minutes':
                            newMeasure.convertedPrice = price * 60
                        if newMeasure.newMeasureTime == 'Days' or  newMeasure.newMeasureTime == 'Day':
                            newMeasure.convertedPrice = price * 0.041
                        if newMeasure.newMeasureTime == 'Weeks' or  newMeasure.newMeasureTime == 'Week':
                            newMeasure.convertedPrice = price * 0.0059
                        if newMeasure.newMeasureTime == 'Years':
                            newMeasure.convertedPrice = price * 0.00011

                    if measure == 'Days' or measure == 'Day':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureTime == 'Minutes':
                            newMeasure.convertedPrice = price * 1440
                        if newMeasure.newMeasureTime == 'Hours' or newMeasure.newMeasureTime == 'Hour':
                            newMeasure.convertedPrice = price * 24
                        if newMeasure.newMeasureTime == 'Weeks' or  newMeasure.newMeasureTime == 'Week':
                            newMeasure.convertedPrice = price * 0.14
                        if newMeasure.newMeasureTime == 'Years':
                            newMeasure.convertedPrice = price * 0.0027

                    if measure == 'Weeks' or measure == 'Week':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureTime == 'Minutes':
                            newMeasure.convertedPrice = price * 10080
                        if newMeasure.newMeasureTime == 'Hours' or newMeasure.newMeasureTime == 'Hour':
                            newMeasure.convertedPrice = price * 168
                        if newMeasure.newMeasureTime == 'Days' or  newMeasure.newMeasureTime == 'Day':
                            newMeasure.convertedPrice = price * 7
                        if newMeasure.newMeasureTime == 'Years':
                            newMeasure.convertedPrice = price * 0.019

                    if measure == 'Years':
                        newMeasure.convertedPrice = price
                        if newMeasure.newMeasureTime == 'Minutes':
                            newMeasure.convertedPrice = price * 525949
                        if newMeasure.newMeasureTime == 'Hours' or newMeasure.newMeasureTime == 'Hour':
                            newMeasure.convertedPrice = price * 8765.81
                        if newMeasure.newMeasureTime == 'Days' or  newMeasure.newMeasureTime == 'Day':
                            newMeasure.convertedPrice = price * 365.242
                        if newMeasure.newMeasureTime == 'Weeks' or  newMeasure.newMeasureTime == 'Week':
                            newMeasure.convertedPrice = price * 52.1775

                    request.session['new_measure'] = newMeasure.newMeasureTime
                    new_measure = newMeasure.newMeasureTime

                request.session['new_price'] = newMeasure.convertedPrice
                return HttpResponseRedirect('/project/programs/costs/umconverter.html')
            else:
                print form.errors

        if 'use' in request.POST:
            price_id = request.session['price_id']
            return HttpResponseRedirect('/project/programs/costs/'+ price_id + '/nonper_indices.html')

    else:
        if measure == 'Other' or measureType == 'mylist':
           form = UMConverter(initial={'convertedPrice':new_price,'newMeasure':new_measure})
        elif measureType == 'listVol':
           form = UMConverter(initial={'convertedPrice':new_price,'newMeasureVol':new_measure})
        elif measureType == 'listLen':
           form = UMConverter(initial={'convertedPrice':new_price,'newMeasureLen':new_measure})
        elif measureType == 'listTime':
           form = UMConverter(initial={'convertedPrice':new_price,'newMeasureTime':new_measure})

    return render_to_response('project/programs/costs/umconverter.html',{'form':form, 'price':price,'measure':measure,'measureType':measureType, 'new_price' : new_price, 'new_measure' : new_measure, 'price_id':price_id},context)

def wage_converter(request):
    context = RequestContext(request)
    price_id = request.session['price_id']

    if 'price' in request.session:
       price = float(request.session['price'])
    else:
       price = 0.0
       request.session['price'] = 0.0

    if 'measure' in request.session:
       measure = request.session['measure'] 
    else:
       measure = ''
       request.session['measure'] = ''

    project_id = request.session['project_id']
    if 'hrsCalendarYr' in request.session:
       hrsCalendarYr = request.session['hrsCalendarYr']
    else:
        try:
            sett = m.Settings.objects.get(projectId=project_id)
            hrsCalendarYr = sett.hrsCalendarYr
            request.session['hrsCalendarYr'] = hrsCalendarYr
            objExists = True
        except ObjectDoesNotExist:
            hrsCalendarYr = 2080
            request.session['hrsCalendarYr'] = hrsCalendarYr
            objExists = False

    if 'hrsAcademicYr' in request.session:
       hrsAcademicYr = request.session['hrsAcademicYr']
    else:
        if objExists:
            hrsAcademicYr = sett.hrsAcademicYr
            request.session['hrsAcademicYr'] = hrsAcademicYr
        else:
            hrsAcademicYr = 1440
            request.session['hrsAcademicYr'] = hrsAcademicYr

    if 'hrsHigherEdn' in request.session:
       hrsHigherEdn = request.session['hrsHigherEdn']
    else:
        if objExists:
            hrsHigherEdn = sett.hrsHigherEdn
            request.session['hrsHigherEdn'] = hrsHigherEdn
        else:
            hrsHigherEdn = 1560
            request.session['hrsHigherEdn'] = hrsHigherEdn

    hrsCalendarYr = float(hrsCalendarYr)
    hrsAcademicYr = float(hrsAcademicYr)
    hrsHigherEdn = float(hrsHigherEdn)

    if 'new_price' in request.session:
        new_price = request.session['new_price']
    else:  
        new_price = round(float(price),3)
        request.session['new_price'] = new_price

    if 'new_measure' in request.session:
        new_measure = request.session['new_measure']
    else:  
        new_measure = measure
        request.session['new_measure'] = measure

    if request.method == 'POST':
        if 'compute' in request.POST:
            form = WageConverter(data=request.POST)
            if form.is_valid():
                newMeasure = form.save(commit=False)
                if measure == 'Hour':
                    newMeasure.convertedPrice = price 
                    if newMeasure.newMeasure == 'Day':
                        newMeasure.convertedPrice = price * 8
                    if newMeasure.newMeasure == 'Week':
                        newMeasure.convertedPrice = price * 40
                    if newMeasure.newMeasure == 'Calendar Year':
                        newMeasure.convertedPrice = price * hrsCalendarYr
                    if newMeasure.newMeasure == 'K-12 Academic Year':
                        newMeasure.convertedPrice = price * hrsAcademicYr
                    if newMeasure.newMeasure == 'Higher Ed Academic Year':
                        newMeasure.convertedPrice = price * hrsHigherEdn

                if measure == 'Day': 
                    newMeasure.convertedPrice = price
                    if newMeasure.newMeasure == 'Hour':
                        newMeasure.convertedPrice = price /  8
                    if newMeasure.newMeasure == 'Week':
                        newMeasure.convertedPrice = price *  5
                    if newMeasure.newMeasure == 'Calendar Year':
                        newMeasure.convertedPrice = price * (hrsCalendarYr / 8)
                    if newMeasure.newMeasure == 'K-12 Academic Year':
                        newMeasure.convertedPrice = price * (hrsAcademicYr / 8)
                    if newMeasure.newMeasure == 'Higher Ed Academic Year':
                        newMeasure.convertedPrice = price * (hrsHigherEdn / 8)

                if measure == 'Week': 
                    newMeasure.convertedPrice = price
                    if newMeasure.newMeasure == 'Hour':
                        newMeasure.convertedPrice = price / 40
                    if newMeasure.newMeasure == 'Day':
                        newMeasure.convertedPrice = price /  5
                    if newMeasure.newMeasure == 'Calendar Year':
                        newMeasure.convertedPrice = price * 52
                    if newMeasure.newMeasure == 'K-12 Academic Year':
                        newMeasure.convertedPrice = price * 36
                    if newMeasure.newMeasure == 'Higher Ed Academic Year':
                        newMeasure.convertedPrice = price * 39

                if measure == 'Calendar Year':
                    newMeasure.convertedPrice = price
                    if newMeasure.newMeasure == 'Hour':
                        newMeasure.convertedPrice = price / hrsCalendarYr
                    if newMeasure.newMeasure == 'Day':
                        newMeasure.convertedPrice = price / (hrsCalendarYr / 8)
                    if newMeasure.newMeasure == 'Week':
                        newMeasure.convertedPrice = price / 52
                    if newMeasure.newMeasure == 'K-12 Academic Year':
                        newMeasure.convertedPrice = price * (hrsAcademicYr / hrsCalendarYr)
                    if newMeasure.newMeasure == 'Higher Ed Academic Year':
                        newMeasure.convertedPrice = price * (hrsHigherEdn / hrsCalendarYr)

                if measure == 'K-12 Academic Year':
                    newMeasure.convertedPrice = price
                    if newMeasure.newMeasure == 'Hour':
                        newMeasure.convertedPrice = price / hrsAcademicYr
                    if newMeasure.newMeasure == 'Day':
                        newMeasure.convertedPrice = price / (hrsAcademicYr / 8)
                    if newMeasure.newMeasure == 'Week':
                        newMeasure.convertedPrice = price / 36
                    if newMeasure.newMeasure == 'Calendar Year':
                        newMeasure.convertedPrice = price * (hrsCalendarYr / hrsAcademicYr)
                    if newMeasure.newMeasure == 'Higher Ed Academic Year':
                        newMeasure.convertedPrice = price * (hrsHigherEdn / hrsAcademicYr)

                if measure == 'Higher Ed Academic Year':
                    newMeasure.convertedPrice = price
                    if newMeasure.newMeasure == 'Hour':
                        newMeasure.convertedPrice = price / hrsHigherEdn
                    if newMeasure.newMeasure == 'Day':
                        newMeasure.convertedPrice = price / (hrsHigherEdn / 8)
                    if newMeasure.newMeasure == 'Week':
                        newMeasure.convertedPrice = price / 39
                    if newMeasure.newMeasure == 'Calendar Year':
                        newMeasure.convertedPrice = price * (hrsCalendarYr / hrsHigherEdn)
                    if newMeasure.newMeasure == 'K-12 Academic Year':
                        newMeasure.convertedPrice = price * (hrsAcademicYr / hrsHigherEdn)

                request.session['new_price'] = round(float(newMeasure.convertedPrice),3)
                request.session['new_measure'] = newMeasure.newMeasure 
                return HttpResponseRedirect('/project/programs/costs/wage_converter.html')
            else:
                print form.errors

        if 'use' in request.POST:
            price_id = request.session['price_id']
            return HttpResponseRedirect('/project/programs/costs/'+ price_id + '/price_indices.html')

    else:
        form = WageConverter(initial={'convertedPrice':new_price,'newMeasure':new_measure})

    return render_to_response('project/programs/costs/wage_converter.html',{'form':form, 'convertedPrice':new_price,'newMeasure':new_measure,'price':price, 'price_id':price_id,'measure':measure, 'hrsCalendarYr': hrsCalendarYr, 'hrsAcademicYr':hrsAcademicYr, 'hrsHigherEdn':hrsHigherEdn},context)
 
def wage_defaults(request):
    context = RequestContext(request)

    if 'hrsCalendarYr' in request.session:
       hrsCalendarYr = request.session['hrsCalendarYr']
    else:   
        try:
            sett = m.Settings.objects.get(projectId=project_id)
            hrsCalendarYr = sett.hrsCalendarYr
            objExists = True 
        except ObjectDoesNotExist:
            hrsCalendarYr = 2080
            objExists = False

    if 'hrsAcademicYr' in request.session:
       hrsAcademicYr = request.session['hrsAcademicYr']
    else:
        if objExists:
            hrsAcademicYr = sett.hrsAcademicYr
        else:
            hrsAcademicYr = 1440

    if 'hrsHigherEdn' in request.session:
       hrsHigherEdn = request.session['hrsHigherEdn']
    else:
        if objExists:
            hrsHigherEdn = sett.hrsHigherEdn
        else:
            hrsHigherEdn = 1560
 
    if request.method == 'POST':
        form = WageDefaults(data=request.POST)
        if form.is_valid():
            benefitRate = form.save(commit=False)
            request.session['hrsCalendarYr'] = benefitRate.hrsCalendarYr
            request.session['hrsAcademicYr'] = benefitRate.hrsAcademicYr
            request.session['hrsHigherEdn'] = benefitRate.hrsHigherEdn
            return HttpResponseRedirect('/project/programs/costs/wage_converter.html')
        else:
            print form.errors
    else:
       form = WageDefaults(initial={'hrsCalendarYr': hrsCalendarYr, 'hrsAcademicYr':hrsAcademicYr, 'hrsHigherEdn':hrsHigherEdn}) 

    return render_to_response('project/programs/costs/wage_defaults.html',{'form':form},context)

def price_benefits(request,price_id):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']                                                                                     
    progname = request.session['programname'] 
    request.session['price_id'] = price_id
    price = m.Prices.objects.get(pk=price_id)

    if 'Rate' in request.session:
        benefitRate = request.session['Rate']
    else:
        if 'benefit_id' in request.session:
            benefit_id = request.session['benefit_id']
            benefit = m.Benefits.objects.get(pk=benefit_id)
            benefitRate = benefit.BenefitRate
        else:
            benefitRate = 0

    if request.method == 'POST':
        form = PriceBenefits(request.POST)
        if form.is_valid():
            benefitRate = form.save(commit=False)
            request.session['Rate'] = benefitRate.benefitRate
            return HttpResponseRedirect('/project/programs/costs/summary.html')
        else:
            print form.errors
            return render_to_response('project/programs/costs/price_benefits.html',{'form':form, 'benefitRate':benefitRate,'price':price, 'project_id':project_id, 'program_id':program_id,'projectname':projectname, 'programname':progname,'form.errors':form.errors},context)
    else:
        form = PriceBenefits()
    return render_to_response('project/programs/costs/price_benefits.html',{'form':form, 'benefitRate':benefitRate,'price':price, 'project_id':project_id, 'program_id':program_id,'projectname':projectname, 'programname':progname},context)

def benefits(request):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    if 'price_id' in request.session:
       price_id = request.session['price_id']
    else:
       price_id = ''
    allbenefits = m.Benefits.objects.all()
    return render(request,'project/programs/costs/benefits.html', {'project_id':project_id, 'program_id':program_id, 'allbenefits' : allbenefits, 'price_id':price_id})

def save_benefit(request,ben_id):
    context = RequestContext(request)
    request.session['benefit_id'] = ben_id
    if 'price_id' in request.session:
       price_id = request.session['price_id']
    else:
       price_id = ''
    return HttpResponseRedirect('/project/programs/costs/'+ price_id +'/price_benefits.html')

def price_summary(request):
    context = RequestContext(request)
    if 'price_id' in request.session:
       price_id = request.session['price_id']
    else:
       price_id = ''
    price = m.Prices.objects.get(pk=price_id)
    
    if 'Rate' in request.session:
       Rate = request.session['Rate']
    else:
       Rate = ''

    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']
    progname = request.session['programname']

    pcount = 0

    if 'new_price' in request.session:
       new_price = request.session['new_price']
    else:
       new_price = price.price

    if 'new_measure' in request.session:
       new_measure = request.session['new_measure']
    else:
       new_measure = price.unitMeasurePrice

    if 'benefit_id' in request.session:
        benefit = m.Benefits.objects.get(pk=request.session['benefit_id'])
        SourceBenefitData = benefit.SourceBenefitData
        YearBenefit = benefit.YearBenefit
    else:
        SourceBenefitData = ''
        YearBenefit = ''

    try:
       sett = m.Settings.objects.get(projectId=request.session['project_id'])
       discountRateEstimates = sett.discountRateEstimates
       infEstimate = m.InflationIndices.objects.get(projectId=request.session['project_id'],yearCPI=sett.yearEstimates)
       geoEstimate = m.GeographicalIndices.objects.get(projectId=request.session['project_id'],stateIndex=sett.stateEstimates,areaIndex=sett.areaEstimates)
       geoEst = geoEstimate.geoIndex
    except ObjectDoesNotExist:
       discountRateEstimates = 3.5
       infEstimate = m.InflationIndices.objects.get(projectId=request.session['project_id']).latest('yearCPI')
       geoEst = 100

    try:
       inf = m.InflationIndices.objects.get(projectId=request.session['project_id'],yearCPI=price.yearPrice)
       infinf = inf.indexCPI
    except ObjectDoesNotExist:
       infinf = 700

    try:
       geo = m.GeographicalIndices.objects.get(projectId=request.session['project_id'],stateIndex=price.statePrice,areaIndex=price.areaPrice)
       geoIndex = geo.geoIndex
    except ObjectDoesNotExist:
       geoIndex = '100'  

    try:
       programdesc = m.ProgramDesc.objects.get(programId = request.session['program_id'])
       pcount = m.ParticipantsPerYear.objects.filter(programdescId_id=programdesc.id).count()
       numberofparticipants = programdesc.numberofparticipants
    except ObjectDoesNotExist:
       pcount = 0
       numberofparticipants = 1

    rowcount = 0

    if pcount > 0:
       MFormSet = modelformset_factory(m.Ingredients, form=PriceSummary, extra=pcount)
       if request.method == 'POST':
          form = MFormSet(request.POST, request.FILES)
          if form.is_valid():
             ingredients = form.save(commit=False)
             for ingredient in ingredients:
                 ingredient.variableFixed = request.POST.get('variableFixed2')  
                 ingredient.category = price.category
                 ingredient.ingredient = price.ingredient
                 ingredient.edLevel = price.edLevel
                 ingredient.sector = price.sector
                 ingredient.unitMeasurePrice = price.unitMeasurePrice
                 ingredient.price = price.price
                 ingredient.sourcePriceData = price.sourcePriceData
                 ingredient.urlPrice = price.urlPrice
                 ingredient.newMeasure = new_measure
                 ingredient.convertedPrice = new_price
                 ingredient.benefitRate = round(float(Rate.strip('"')),2)
                 ingredient.SourceBenefitData = SourceBenefitData
                 ingredient.YearBenefit = YearBenefit
                 ingredient.yearPrice = price.yearPrice
                 ingredient.statePrice = price.statePrice
                 ingredient.areaPrice = price.areaPrice
                 ingredient.lifetimeAsset = 1
                 ingredient.interestRate = 0.0
                 ingredient.percentageofUsage = 100
                 ingredient.indexCPI = infinf
                 ingredient.geoIndex = geoIndex
                 ingredient.programId = request.session['program_id']
                 ingredient.priceAdjAmortization = float(new_price)
                 ingredient.priceAdjBenefits = ingredient.priceAdjAmortization * (1 + float(ingredient.benefitRate)/100)
                 ingredient.priceAdjInflation = ingredient.priceAdjBenefits * (float(infEstimate.indexCPI) / float(infinf))
                 ingredient.priceAdjGeographicalArea = ingredient.priceAdjInflation * (float(geoEst) / float(geoIndex))
                 ingredient.priceNetPresentValue = ingredient.priceAdjGeographicalArea * math.exp((1- ingredient.yearQtyUsed) * (discountRateEstimates/100))
                 ingredient.adjPricePerIngredient = ingredient.priceNetPresentValue
                 ingredient.costPerIngredient = ingredient.adjPricePerIngredient * float(ingredient.quantityUsed) * (100/100)
                 try:
                    partperyear = m.ParticipantsPerYear.objects.get(programdescId_id=programdesc.id, yearnumber=ingredient.yearQtyUsed)
                    ingredient.costPerParticipant = float(ingredient.costPerIngredient) / float(partperyear.noofparticipants)
                 except ObjectDoesNotExist:
                    ingredient.costPerParticipant = ''
                 ingredient.save()
                 rowcount = rowcount + 1
             if rowcount == 0:
                 form = PriceSummary(request.POST)
                 if form.is_valid():
                    ingredient = form.save(commit=False)
                    ingredient.category = price.category
                    ingredient.ingredient = price.ingredient
                    ingredient.edLevel = price.edLevel
                    ingredient.sector = price.sector
                    ingredient.unitMeasurePrice = price.unitMeasurePrice
                    ingredient.price = price.price
                    ingredient.sourcePriceData = price.sourcePriceData
                    ingredient.urlPrice = price.urlPrice
                    ingredient.newMeasure = new_measure
                    ingredient.convertedPrice = new_price
                    ingredient.benefitRate = round(float(Rate.strip('"')),2)
                    ingredient.SourceBenefitData = SourceBenefitData
                    ingredient.YearBenefit = YearBenefit
                    ingredient.yearPrice = price.yearPrice
                    ingredient.statePrice = price.statePrice
                    ingredient.areaPrice = price.areaPrice
                    ingredient.yearQtyUsed = 1
                    ingredient.lifetimeAsset = 1
                    ingredient.interestRate = 0.0
                    ingredient.percentageofUsage = 100
                    ingredient.indexCPI = infinf
                    ingredient.geoIndex = geoIndex
                    ingredient.programId = request.session['program_id']
                    ingredient.priceAdjAmortization = float(new_price)
                    ingredient.priceAdjBenefits = ingredient.priceAdjAmortization * (1 + float(ingredient.benefitRate)/100)
                    ingredient.priceAdjInflation = ingredient.priceAdjBenefits * (float(infEstimate.indexCPI) / float(infinf))
                    ingredient.priceAdjGeographicalArea = ingredient.priceAdjInflation * (float(geoEst) / float(geoIndex))
                    ingredient.priceNetPresentValue = ingredient.priceAdjGeographicalArea * math.exp((1- ingredient.yearQtyUsed) * (discountRateEstimates/100))
                    ingredient.adjPricePerIngredient = ingredient.priceNetPresentValue
                    ingredient.costPerIngredient = ingredient.adjPricePerIngredient * float(ingredient.quantityUsed) * (100/100)
                    if numberofparticipants is not None:
                       ingredient.costPerParticipant = float(ingredient.costPerIngredient) / float(numberofparticipants) 
                    ingredient.save()

             totalCost = 0
             ing =  m.Ingredients.objects.filter(programId = request.session['program_id'])
             for i in ing:
                totalCost = totalCost + i.costPerIngredient

             for i in ing:
                i.totalCost = totalCost
                i.percentageCost = i.costPerIngredient * 100/i.totalCost
                if numberofparticipants is not None:
                   i.averageCost = float(i.totalCost) / float(numberofparticipants)
                   i.save(update_fields=['totalCost','averageCost','percentageCost'])
                else:                                                                                                                
                   i.save(update_fields=['totalCost','percentageCost'])

             return HttpResponseRedirect('/project/programs/effect/'+ project_id + '/' + program_id + '/tabbedview.html?activeform=costform')
             
          else:
             print form.errors
             return render_to_response('project/programs/costs/summary.html',{'project_id':project_id, 'program_id':program_id, 'pcount':pcount,'form':form, 'price':price, 'Rate':Rate, 'new_price':new_price,'new_measure':new_measure,'projectname':projectname, 'programname':progname,'form.errors':form.errors},context)
       else:
          form = MFormSet(queryset=m.Ingredients.objects.none(),initial=[{'yearQtyUsed': "%d" % (i+1)} for i in range(10)])
    else:
       if request.method == 'POST':
          form = PriceSummary(request.POST)
          if form.is_valid():
             ingredient = form.save(commit=False)
             ingredient.category = price.category
             ingredient.ingredient = price.ingredient
             ingredient.edLevel = price.edLevel
             ingredient.sector = price.sector
             ingredient.unitMeasurePrice = price.unitMeasurePrice
             ingredient.price = price.price
             ingredient.sourcePriceData = price.sourcePriceData
             ingredient.urlPrice = price.urlPrice
             ingredient.newMeasure = new_measure
             ingredient.convertedPrice = float(new_price)
             ingredient.benefitRate = round(float(Rate.strip('"')),2)
             ingredient.SourceBenefitData = SourceBenefitData
             ingredient.YearBenefit = YearBenefit
             ingredient.yearPrice = price.yearPrice
             ingredient.statePrice = price.statePrice
             ingredient.areaPrice = price.areaPrice
             ingredient.lifetimeAsset = 1
             ingredient.yearQtyUsed = 1    
             ingredient.interestRate = 0.0
             ingredient.percentageofUsage = 100
             ingredient.indexCPI = infinf
             ingredient.geoIndex = geoIndex
             ingredient.programId = request.session['program_id']
             ingredient.priceAdjAmortization = float(new_price)
             ingredient.priceAdjBenefits = ingredient.priceAdjAmortization * (1 + float(ingredient.benefitRate)/100)
             ingredient.priceAdjInflation = ingredient.priceAdjBenefits * (float(infEstimate.indexCPI) / float(infinf))
             ingredient.priceAdjGeographicalArea = ingredient.priceAdjInflation * (float(geoEst) / float(ingredient.geoIndex))
             ingredient.priceNetPresentValue = ingredient.priceAdjGeographicalArea * math.exp((1-ingredient.yearQtyUsed) *(discountRateEstimates/100))
             ingredient.adjPricePerIngredient = ingredient.priceNetPresentValue
             ingredient.costPerIngredient = ingredient.adjPricePerIngredient * float(ingredient.quantityUsed) * (100/100)
             if numberofparticipants is not None:
                ingredient.costPerParticipant = float(ingredient.costPerIngredient) / float(numberofparticipants)

             ingredient.save()

             total_cost = 0
             ing = m.Ingredients.objects.filter(programId = request.session['program_id'])
             for i in ing:
                total_cost = total_cost + i.costPerIngredient
             for i in ing:
                i.totalCost = total_cost
                i.percentageCost = i.costPerIngredient * 100 / i.totalCost
                if numberofparticipants is not None:
                   i.averageCost = float(i.totalCost) / float(numberofparticipants)
                   i.save(update_fields=['totalCost','averageCost','percentageCost'])
                else:
                   i.save(update_fields=['totalCost','percentageCost'])
             return HttpResponseRedirect('/project/programs/effect/'+ project_id +'/' + program_id + '/tabbedview.html?activeform=costform')
          else:
             print form.errors

       else:
          form = PriceSummary()
    return render_to_response('project/programs/costs/summary.html',{'project_id':project_id, 'program_id':program_id, 'pcount':pcount,'form':form, 'price':price, 'Rate':Rate, 'new_price':new_price,'projectname':projectname, 'programname':progname,'new_measure':new_measure},context)
 
def nonper_summary(request):
    context = RequestContext(request)
    if 'price_id' in request.session:
       price_id = request.session['price_id']
    else:
       price_id = ''

    if 'Rate' in request.session:
       Rate = request.session['Rate']
    else:
       Rate = ''

    project_id = request.session['project_id']
    program_id = request.session['program_id']
    projectname = request.session['projectname']
    progname = request.session['programname']
    
    pcount = 0
    rowcount = 0

    if 'lifetimeAsset' in request.session:
       lifetimeAsset = request.session['lifetimeAsset']
    else:
       lifetimeAsset = 1.0

    if 'interestRate' in request.session:
       interestRate = request.session['interestRate']
    else:    
       interestRate = 0.0

    price = m.Prices.objects.get(pk=price_id)
    if 'new_price' in request.session:
       new_price = request.session['new_price']
    else:
       new_price = price.price

    if 'new_measure' in request.session:
       new_measure = request.session['new_measure']
    else:
       new_measure = price.unitMeasurePrice

    try:
       sett = m.Settings.objects.get(projectId=request.session['project_id'])
       discountRateEstimates = sett.discountRateEstimates
       infEstimate = m.InflationIndices.objects.get(projectId=request.session['project_id'],yearCPI=sett.yearEstimates)
       geoEstimate = m.GeographicalIndices.objects.get(projectId=request.session['project_id'],stateIndex=sett.stateEstimates,areaIndex=sett.areaEstimates)
       geoEst = geoEstimate.geoIndex
    except ObjectDoesNotExist:
       discountRateEstimates = 3.5
       infEstimate = m.InflationIndices.objects.get(projectId=request.session['project_id']).latest('yearCPI')
       geoEst = 100

    try:
       inf = m.InflationIndices.objects.get(projectId=request.session['project_id'],yearCPI=price.yearPrice)
       infinf = inf.indexCPI
    except ObjectDoesNotExist:
       infinf = 700

    try: 
       geo = m.GeographicalIndices.objects.get(projectId=request.session['project_id'],stateIndex=price.statePrice,areaIndex=price.areaPrice)
       geoIndex = geo.geoIndex
    except ObjectDoesNotExist:
       geoIndex = 100 

    try:
       programdesc = m.ProgramDesc.objects.get(programId = request.session['program_id'])
       pcount = m.ParticipantsPerYear.objects.filter(programdescId_id=programdesc.id).count()
       numberofparticipants = programdesc.numberofparticipants
    except ObjectDoesNotExist:
       pcount = 0
       numberofparticipants = 1
    if pcount > 0:
       MFormSet = modelformset_factory(m.Ingredients, form=MultipleSummary,extra=pcount)
       if request.method == 'POST':
          form = MFormSet(request.POST, request.FILES)
          if form.is_valid():
             ingredients = form.save(commit=False)
             #for ingredient in ingredients:
                #if ingredient.quantityUsed is not None:
                   #rowcount = rowcount + 1
             #if rowcount == 0:
                #raise ValueError('error') 
                    
             for ingredient in ingredients:
                 ingredient.variableFixed = request.POST.get('variableFixed2')
                 ingredient.category = price.category
                 ingredient.ingredient = price.ingredient
                 ingredient.edLevel = price.edLevel
                 ingredient.sector = price.sector
                 ingredient.unitMeasurePrice = price.unitMeasurePrice
                 ingredient.price = price.price
                 ingredient.sourcePriceData = price.sourcePriceData
                 ingredient.urlPrice = price.urlPrice
                 ingredient.newMeasure = new_measure
                 ingredient.convertedPrice = float(new_price)
                 ingredient.yearPrice = price.yearPrice
                 ingredient.statePrice = price.statePrice
                 ingredient.areaPrice = price.areaPrice
                 ingredient.programId = request.session['program_id']
                 ingredient.lifetimeAsset = lifetimeAsset
                 ingredient.interestRate = interestRate
                 ingredient.benefitRate = 0.0
                 ingredient.indexCPI = infinf
                 ingredient.geoIndex = geoIndex
                 if ingredient.lifetimeAsset is None:
                    ingredient.lifetimeAsset = 1
                 if ingredient.interestRate is None or ingredient.interestRate == '0':
                    ingredient.interestRate = 0.0
                 if ingredient.interestRate == '0.0':
                    ingredient.priceAdjAmortization = ingredient.convertedPrice / float(ingredient.lifetimeAsset)
                 else:
                    ingredient.priceAdjAmortization = ingredient.convertedPrice * ((float(interestRate)/100)*math.pow((1+(float(interestRate)/100)),float(lifetimeAsset)))/ (math.pow((1+(float(interestRate)/100)),float(lifetimeAsset))-1)
                 ingredient.priceAdjBenefits = ingredient.priceAdjAmortization
                 ingredient.priceAdjInflation = ingredient.priceAdjBenefits * (float(infEstimate.indexCPI) / float(infinf))
                 ingredient.priceAdjGeographicalArea = ingredient.priceAdjInflation * (float(geoEst) / float(geoIndex))
                 ingredient.priceNetPresentValue = ingredient.priceAdjGeographicalArea * math.exp((1- ingredient.yearQtyUsed) * (discountRateEstimates/100))
                 ingredient.adjPricePerIngredient = ingredient.priceNetPresentValue
                 if ingredient.quantityUsed is None and ingredient.percentageofUsage is None:
                    ingredient.costPerIngredient = 0.0
                 else:
                    if ingredient.percentageofUsage == 100:
                       ingredient.costPerIngredient = round(ingredient.adjPricePerIngredient,3) * float(ingredient.quantityUsed)
                    else:
                       ingredient.costPerIngredient = ingredient.adjPricePerIngredient * float(ingredient.quantityUsed) * (float(ingredient.percentageofUsage)/100)
                 try:
                    partperyear = m.ParticipantsPerYear.objects.get(programdescId_id=programdesc.id, yearnumber=ingredient.yearQtyUsed)
                    ingredient.costPerParticipant = float(ingredient.costPerIngredient) / float(partperyear.noofparticipants)
                 except ObjectDoesNotExist:
                    ingredient.costPerParticipant = ''
                 ingredient.save()
                 rowcount = rowcount + 1

             if rowcount == 0:
                form = MultipleSummary(request.POST)
                if form.is_valid():
                   ingredient = form.save(commit=False)
                   ingredient.category = price.category
                   ingredient.ingredient = price.ingredient
                   ingredient.edLevel = price.edLevel
                   ingredient.sector = price.sector
                   ingredient.unitMeasurePrice = price.unitMeasurePrice
                   ingredient.price = price.price
                   ingredient.sourcePriceData = price.sourcePriceData
                   ingredient.urlPrice = price.urlPrice
                   ingredient.newMeasure = new_measure
                   ingredient.convertedPrice = float(new_price)
                   ingredient.yearPrice = price.yearPrice
                   ingredient.statePrice = price.statePrice
                   ingredient.areaPrice = price.areaPrice
                   ingredient.programId = request.session['program_id']
                   ingredient.lifetimeAsset = lifetimeAsset
                   ingredient.interestRate = interestRate
                   ingredient.benefitRate = 0.0
                   ingredient.indexCPI = infinf
                   if ingredient.yearQtyUsed is None:
                      ingredient.yearQtyUsed = 1                       
                   if ingredient.lifetimeAsset is None:
                      ingredient.lifetimeAsset = 1
                   if ingredient.interestRate is None:
                      ingredient.interestRate = 0.0
                   if ingredient.interestRate == '0.0':
                      ingredient.priceAdjAmortization = float(ingredient.convertedPrice) / float(ingredient.lifetimeAsset)
                   else:
                      ingredient.priceAdjAmortization = ingredient.convertedPrice * ((float(interestRate)/100)*math.pow((1+(float(interestRate)/100)),float(lifetimeAsset))/ (math.pow((1+(float(interestRate)/100)),float(lifetimeAsset))-1))
                   ingredient.priceAdjBenefits = ingredient.priceAdjAmortization
                   ingredient.priceAdjInflation = ingredient.priceAdjBenefits * (float(infEstimate.indexCPI) / float(infinf))
                   ingredient.priceAdjGeographicalArea = ingredient.priceAdjInflation * (float(geoEst) / float(geoIndex))
                   ingredient.priceNetPresentValue = ingredient.priceAdjGeographicalArea * math.exp(1 * discountRateEstimates/100)
                   ingredient.adjPricePerIngredient = ingredient.priceNetPresentValue
                   if ingredient.percentageofUsage == 100:
                      ingredient.costPerIngredient = round(ingredient.adjPricePerIngredient,3) * float(ingredient.quantityUsed)
                   else:   
                      ingredient.costPerIngredient = ingredient.adjPricePerIngredient * float(ingredient.quantityUsed) * (float(ingredient.percentageofUsage)/100)
                   if numberofparticipants is not None:
                      ingredient.costPerParticipant = float(ingredient.costPerIngredient) / float(numberofparticipants) 
                   ingredient.save()

             totalCost = 0
             ing = m.Ingredients.objects.filter(programId = program_id) 
             for i in ing:
                totalCost = totalCost + i.costPerIngredient

             for i in ing:
                i.totalCost = totalCost
                i.percentageCost = i.costPerIngredient * 100/i.totalCost
                if numberofparticipants is not None:
                   i.averageCost = float(i.totalCost) / float(numberofparticipants)  
                   i.save(update_fields=['totalCost','averageCost','percentageCost'])
                else:
                   i.save(update_fields=['totalCost','percentageCost'])                
             return HttpResponseRedirect('/project/programs/effect'+ '/' + project_id + '/' + program_id + '/tabbedview.html?activeform=costform')
          else:
             print form.errors

       else:
          form = MFormSet(queryset=m.Ingredients.objects.none(),initial=[{'yearQtyUsed': "%d" % (i+1)} for i in range(10)])
    else:
       if request.method == 'POST':
          form = MultipleSummary(request.POST)
          if form.is_valid():
             ingredient = form.save(commit=False)
             ingredient.category = price.category
             ingredient.ingredient = price.ingredient
             ingredient.edLevel = price.edLevel
             ingredient.sector = price.sector
             ingredient.unitMeasurePrice = price.unitMeasurePrice
             ingredient.price = price.price
             ingredient.sourcePriceData = price.sourcePriceData
             ingredient.urlPrice = price.urlPrice        
             ingredient.newMeasure = new_measure
             ingredient.convertedPrice = float(new_price)
             ingredient.yearPrice = price.yearPrice
             ingredient.statePrice = price.statePrice
             ingredient.areaPrice = price.areaPrice
             ingredient.programId = request.session['program_id']
             ingredient.lifetimeAsset = lifetimeAsset
             ingredient.interestRate = interestRate
             ingredient.benefitRate = 0.0
             ingredient.indexCPI = infinf
             ingredient.geoIndex = geoIndex
             if ingredient.yearQtyUsed is None:
                ingredient.yearQtyUsed = 1 
             if ingredient.lifetimeAsset is None:
                ingredient.lifetimeAsset = 1
             if ingredient.interestRate is None or ingredient.interestRate == '0':
                ingredient.interestRate = 0.0
             if ingredient.interestRate == '0.0':
                 ingredient.priceAdjAmortization = float(ingredient.convertedPrice) / float(ingredient.lifetimeAsset)
             else:
                 ingredient.priceAdjAmortization = ingredient.convertedPrice * ((float(interestRate)/100)*math.pow((1+(float(interestRate)/100)),float(lifetimeAsset)))/ (math.pow((1+(float(interestRate)/100)),float(lifetimeAsset))-1)
             ingredient.priceAdjBenefits = ingredient.priceAdjAmortization
             ingredient.priceAdjInflation = ingredient.priceAdjBenefits * (float(infEstimate.indexCPI) / float(infinf))
             ingredient.priceAdjGeographicalArea = ingredient.priceAdjInflation * (float(geoEst) / float(geoIndex)) 
             ingredient.priceNetPresentValue = ingredient.priceAdjGeographicalArea * math.exp((1 - ingredient.yearQtyUsed) * (discountRateEstimates/100))
             ingredient.adjPricePerIngredient = ingredient.priceNetPresentValue
             if ingredient.percentageofUsage == 100:
                ingredient.costPerIngredient = round(ingredient.adjPricePerIngredient,3) * float(ingredient.quantityUsed)
             else:
                ingredient.costPerIngredient = ingredient.adjPricePerIngredient * float(ingredient.quantityUsed) * (float(ingredient.percentageofUsage)/100)
             if numberofparticipants is not None:
                ingredient.costPerParticipant = float(ingredient.costPerIngredient) / float(numberofparticipants)
             ingredient.save()
             
             total_cost = 0
             ing = m.Ingredients.objects.filter(programId = program_id)
             for i in ing:
                 total_cost = total_cost + i.costPerIngredient
             for i in ing:
                 i.totalCost = total_cost
                 i.percentageCost = i.costPerIngredient * 100/i.totalCost
                 if numberofparticipants is not None:
                    i.averageCost = float(i.totalCost) / float(numberofparticipants)  
                    i.save(update_fields=['totalCost','averageCost','percentageCost'])
                 else:
                    i.save(update_fields=['totalCost','percentageCost'])
             return HttpResponseRedirect('/project/programs/effect/'+project_id+'/'+program_id+'/tabbedview.html?activeform=costform')
          else:
             print form.errors

       else:
          form = MultipleSummary()
    return render_to_response('project/programs/costs/nonper_summary.html',{'project_id':project_id, 'program_id':program_id, 'projectname':projectname, 'programname':progname,'pcount':pcount,'form':form, 'price':price, 'Rate':Rate, 'new_price':new_price,'new_measure':new_measure},context)

def finish(request):
    context = RequestContext(request)
    project_id = request.session['project_id']
    program_id = request.session['program_id']
    if 'price_id' in request.session:
       price_id = request.session['price_id']
    else:
       price_id = ''
    price = m.Prices.objects.get(pk=price_id)
    return render(request,'project/programs/costs/finish.html', {'price':price, 'project_id':project_id, 'program_id':program_id})

def program_list(request,project_id):
    request.session['project_id'] = project_id
    try:
        project = m.Projects.objects.get(pk=project_id)
        program = m.Programs.objects.filter(projectId=project_id)
    except ObjectDoesNotExist:
        return HttpResponse('A Project and/or Program does not exist! Cannot proceed further.')
    return render_to_response(
            'project/programs/program_list.html',
            {'project':project,'program':program})

def index(request):
    two_days_ago = datetime.utcnow() - timedelta(days=2)
    recent_projects = m.Projects.objects.filter(created_at__gt = two_days_ago).all()
    template = loader.get_template('index.html')
 
    context = Context({
        'projects_list' : recent_projects
    })
    return HttpResponse(template.render(context))

def project_detail(request, projects_id):
    try:
        project = m.Projects.objects.get(pk=projects_id)
    except m.Projects.DoesNotExist:
        raise Http404
    return render(request, 'projects/detail.html', {'projects':project})

def project_upload(request):
    if request.method == 'GET':
        return render(request, 'projects/upload.html', {})
    elif request.method == 'POST':
        project = m.Projects.objects.create(projectname=request.POST['projectname'],
                                            typeanalysis=request.POST['typeanalysis'],
                                            created_at=datetime.utcnow())
        return HttpResponseRedirect(reverse('project_detail', kwargs={'projects_id': projects.id}))       

def register(request):
    context = RequestContext(request)

    registered = False

    if request.method == 'POST':
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            user.set_password(user.password)
            user.save()

            profile = profile_form.save(commit=True)
            profile.user = user
            profile.save()

            registered = True

        else:
            print user_form.errors, profile_form.errors

    else:
        user_form = UserForm()
        profile_form = UserProfileForm()

    return render_to_response(
            'register/register.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered},
            context)

def user_login(request):
    context = RequestContext(request)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if user:
            if user.is_active:
                auth_login(request, user)
                return HttpResponseRedirect('/admin/costtool')
            else:
                return HttpResponse("Your account is disabled.")
        else:
            print "Invalid login details: {0}, {1}".format(username, password)
            return HttpResponse("Invalid login details supplied.")

    else:
        return render_to_response('login/login.html', {}, context)

def about(request):
    context = RequestContext(request)
    return render_to_response('about.html', {}, context)

def add_project(request):
    context = RequestContext(request)

    if request.method == 'POST':
        projectform = ProjectsForm(data=request.POST)

        if projectform.is_valid():
            projectname = projectform.save()
            projectname.save()
            for i in m.InflationIndices_orig.objects.all():
                inf =  m.InflationIndices.objects.create(yearCPI=i.yearCPI, indexCPI=i.indexCPI, projectId=projectname.id)
            for g in m.GeographicalIndices_orig.objects.all():
                geo = m.GeographicalIndices.objects.create(stateIndex=g.stateIndex, areaIndex=g.areaIndex, geoIndex=g.geoIndex, projectId=projectname.id)
            latest = m.InflationIndices.objects.all().latest('yearCPI')
            s = m.Settings.objects.create(discountRateEstimates=3.5, yearEstimates = latest.yearCPI, stateEstimates='All states', areaEstimates="All areas", selectDatabase="[u'CBCSE',u'My']",limitEdn="[u'Select',u'General',u'Grades PK', u'Grades K-6', u'Grades 6-8', u'Grades 9-12',u'Grades K-12','PostSecondary']",limitSector="[u'Select',u'Any',u'Public',u'Private']",limitYear="[u'All',u'recent']",hrsCalendarYr=2080,hrsAcademicYr=1440,hrsHigherEdn=1560,projectId=projectname.id) 
            request.session['project_id'] = projectname.id
            return HttpResponseRedirect('/project/settings.html')
            #return render_to_response('project/add_project.html',{'projectform':projectform}, context)
        else:
            print projectform.errors

    else:
        projectform = ProjectsForm()        

    return render_to_response(
            'project/add_project.html',
            {'projectform': projectform}, context)

def project_list(request):
    if 'project_id' in request.session:
        del request.session['project_id']

    if 'program_id' in request.session:
        del request.session['program_id']

    allprojects = m.Projects.objects.all()
    template = loader.get_template('project/project_list.html')
    context = Context({
        'allprojects' : allprojects
    })
    return HttpResponse(template.render(context))

def del_project(request, proj_id):
    context = RequestContext(request)
    m.Projects.objects.get(pk=proj_id).delete()
    return HttpResponseRedirect('/project/project_list.html')

def add_price(request):
    context = RequestContext(request)
    if request.method == 'POST':
        pricesform = PricesForm(data=request.POST)

        if pricesform.is_valid():
            priceProvider = pricesform.save(commit=False)
            priceProvider.priceProvider = 'User'
            priceProvider.save()
            return HttpResponseRedirect('/prices/my_price_list.html')
        else:
            print pricesform.errors

    else:
        pricesform = PricesForm()

    return render_to_response(
            'prices/add_price.html',
            {'pricesform': pricesform}, context)

def view_price(request, price_id):
    price = m.Prices.objects.get(pk=price_id)

    template = loader.get_template('prices/view_price.html')
    context = Context({
        'price' : price
    })
    return HttpResponse(template.render(context))

def edit_price(request, price_id):
    price = m.Prices.objects.get(pk=price_id)
    context = RequestContext(request)

    if request.method == 'POST':
        pricesform = PricesForm(request.POST,instance=price)
        if pricesform.is_valid():
            priceProvider = pricesform.save()
            priceProvider.save()
            return HttpResponseRedirect('/prices/my_price_list.html')
        else:
            print priceform.errors
    else:
        pricesform = PricesForm(instance=price)

    return render_to_response(
            'prices/edit_price.html',
            {'pricesform': pricesform}, context)

def del_price(request, price_id):
    context = RequestContext(request)
    m.Prices.objects.get(pk=price_id).delete()
    return HttpResponseRedirect('/prices/my_price_list.html')

def clear_prices(request):
    context = RequestContext(request)
    m.Prices.objects.filter(priceProvider='User').delete()
    return HttpResponseRedirect('/prices/my_price_list.html')

def price_list(request):
    allprices = m.Prices.objects.filter(priceProvider='CBCSE')

    template = loader.get_template('prices/price_list.html')
    context = Context({'allprices' : allprices})
    return HttpResponse(template.render(context))

def my_price_list(request):
    allprices2 = m.Prices.objects.filter(priceProvider='User')

    template = loader.get_template('prices/my_price_list.html')
    context = Context({'allprices2' : allprices2})
    return HttpResponse(template.render(context))

def import_excel(request):
    # Open the workbook and define the worksheet
    book = xlrd.open_workbook("/home/amritha/costtool/documents/DBofPrices.xls")
    sheet = book.sheet_by_name("Ingredients")
    m.Prices.objects.filter(priceProvider='CBCSE').delete()

    # Establish a MySQL connection
    database = MySQLdb.connect (host="mysql.server", user = "amritha", passwd = "pass", charset="utf8", db = "amritha$costtool")

    # Get the cursor, which is used to traverse the database, line by line
    cursor = database.cursor()
    
    # Create the INSERT INTO sql query
    query = """INSERT INTO costtool_prices (priceProvider,category,ingredient,edLevel,sector,descriptionPrice,unitMeasurePrice,price,yearPrice,statePrice,areaPrice,sourcePriceData,urlPrice,lastChecked,nextCheckDate) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    # Create a For loop to iterate through each row in the XLS file, starting at row 2 to skip the headers
    for r in range(1, sheet.nrows):
        priceProvider      = sheet.cell(r,0).value
        category  = sheet.cell(r,1).value
        ingredient          = sheet.cell(r,2).value
        edLevel     = sheet.cell(r,3).value
        sector       = sheet.cell(r,4).value
        descriptionPrice = sheet.cell(r,5).value
        unitMeasurePrice        = sheet.cell(r,6).value
        price       = sheet.cell(r,7).value
        yearPrice     = sheet.cell(r,8).value
        statePrice        = sheet.cell(r,9).value
        areaPrice         = sheet.cell(r,10).value
        sourcePriceData          = sheet.cell(r,11).value
        urlPrice   = sheet.cell(r,12).value
        lastChecked   = sheet.cell(r,13).value
        nextCheckDate   = sheet.cell(r,14).value

        # Assign values from each row
        values = (priceProvider,category,ingredient,edLevel,sector,descriptionPrice,unitMeasurePrice,price,yearPrice,statePrice,areaPrice,sourcePriceData,urlPrice,lastChecked,nextCheckDate)

        # Execute sql Query
        cursor.execute(query, values)

    # Close the cursor
    cursor.close()

    # Commit the transaction
    database.commit()

    # Close the database connection
    database.close()

    columns = str(sheet.ncols)
    rows = str(sheet.nrows)
    return HttpResponseRedirect('/prices/imports.html')

def import_geo(request):
    # Open the workbook and define the worksheet
    book = xlrd.open_workbook("/home/amritha/costtool/documents/GeographicalIndex.xlsx")
    sheet = book.sheet_by_name("Sheet1")
    m.GeographicalIndices_orig.objects.all().delete()

    # Establish a MySQL connection
    database = MySQLdb.connect (host="mysql.server", user = "amritha", passwd = "pass", charset="utf8", db = "amritha$costtool")

    # Get the cursor, which is used to traverse the database, line by line
    cursor = database.cursor()

    # Create the INSERT INTO sql query
    query = """INSERT INTO costtool_geographicalindices_orig (stateIndex, areaIndex, geoIndex) VALUES (%s, %s, %s)"""

    # Create a For loop to iterate through each row in the XLS file, starting at row 2 to skip the headers
    for r in range(1, sheet.nrows):
        stateIndex      = sheet.cell(r,0).value
        areaIndex  = sheet.cell(r,1).value
        geoIndex          = sheet.cell(r,2).value
        
        # Assign values from each row
        values = (stateIndex, areaIndex, geoIndex)

        # Execute sql Query
        cursor.execute(query, values)

    # Close the cursor
    cursor.close()

    # Commit the transaction
    database.commit()

    # Close the database connection
    database.close()

    columns = str(sheet.ncols)
    rows = str(sheet.nrows)
    return HttpResponseRedirect('/prices/imports.html')

def import_inf(request):
    # Open the workbook and define the worksheet
    book = xlrd.open_workbook("/home/amritha/costtool/documents/InflationIndex.xlsx")
    sheet = book.sheet_by_name("Sheet1")
    m.InflationIndices_orig.objects.all().delete()

    # Establish a MySQL connection
    database = MySQLdb.connect (host="mysql.server", user = "amritha", passwd = "pass", charset="utf8", db = "amritha$costtool")

    # Get the cursor, which is used to traverse the database, line by line
    cursor = database.cursor()

    # Create the INSERT INTO sql query
    query = """INSERT INTO costtool_inflationindices_orig (yearCPI, indexCPI) VALUES (%s, %s)"""

    # Create a For loop to iterate through each row in the XLS file, starting at row 2 to skip the headers
    for r in range(1, sheet.nrows):
        yearCPI      = sheet.cell(r,0).value
        indexCPI  = sheet.cell(r,1).value

        # Assign values from each row
        values = (yearCPI, indexCPI)

        # Execute sql Query
        cursor.execute(query, values)

    # Close the cursor
    cursor.close()

    # Commit the transaction
    database.commit()

    # Close the database connection
    database.close()

    columns = str(sheet.ncols)
    rows = str(sheet.nrows)
    return HttpResponseRedirect('/prices/imports.html')

def import_benefits(request):
    # Open the workbook and define the worksheet
    book = xlrd.open_workbook("/home/amritha/costtool/documents/Benefits.xlsx")
    sheet = book.sheet_by_name("Sheet1")
    m.Benefits.objects.all().delete()

    # Establish a MySQL connection
    database = MySQLdb.connect (host="mysql.server", user = "amritha", passwd = "pass", charset="utf8", db = "amritha$costtool")

    # Get the cursor, which is used to traverse the database, line by line
    cursor = database.cursor()

    # Create the INSERT INTO sql query
    query = """INSERT INTO costtool_benefits (SectorBenefit, EdLevelBenefit, PersonnelBenefit, TypeRateBenefit,	YearBenefit, BenefitRate, SourceBenefitData, URLBenefitData) VALUES (%s, %s,%s, %s,%s, %s,%s, %s)"""

    # Create a For loop to iterate through each row in the XLS file, starting at row 2 to skip the headers
    for r in range(1, sheet.nrows):
        SectorBenefit      = sheet.cell(r,0).value
        EdLevelBenefit  = sheet.cell(r,1).value
        PersonnelBenefit = sheet.cell(r,2).value
        TypeRateBenefit      = sheet.cell(r,3).value
        YearBenefit = sheet.cell(r,4).value
        BenefitRate  = sheet.cell(r,5).value
        SourceBenefitData      = sheet.cell(r,6).value
        URLBenefitData  = sheet.cell(r,7).value

        # Assign values from each row
        values = (SectorBenefit, EdLevelBenefit, PersonnelBenefit, TypeRateBenefit, YearBenefit, BenefitRate, SourceBenefitData, URLBenefitData)

        # Execute sql Query
        cursor.execute(query, values)

    # Close the cursor
    cursor.close()

    # Commit the transaction
    database.commit()

    # Close the database connection
    database.close()

    columns = str(sheet.ncols)
    rows = str(sheet.nrows)
    return HttpResponseRedirect('/prices/imports.html')

def add_settings(request,project_id):
    request.session['project_id'] = project_id
    proj = m.Projects.objects.get(pk = project_id)
    context = RequestContext(request)
    result = 0
    try:
       setrec = m.Settings.objects.get(projectId=project_id)
       objectexists = True
       before_year = setrec.yearEstimates
       before_disc = setrec.discountRateEstimates
       before_state = setrec.stateEstimates
       before_area = setrec.areaEstimates
    except ObjectDoesNotExist:
       objectexists = False
    
    if request.method == 'POST':
        if objectexists:
           setform = SettingsForm(request.POST, instance=setrec)
        else:
           setform = SettingsForm(request.POST)
        
        if setform.is_valid():
            discountRateEstimates = setform.save(commit=False)
            discountRateEstimates.projectId = project_id
            discountRateEstimates.save()
            if objectexists:
               if (before_year != discountRateEstimates.yearEstimates) or (before_disc != discountRateEstimates.discountRateEstimates) or (before_state != discountRateEstimates.stateEstimates) or (before_area != discountRateEstimates.areaEstimates): 
                  result = calculations(project_id)
            return HttpResponseRedirect('/project/project_list.html')
        else:
            print setform.errors

    else:
        if objectexists:
           setform = SettingsForm(instance=setrec)
        else:
           setform = SettingsForm()

    return render_to_response(
            'project/add_settings.html',
            {'frm1': setform, 'projname':proj.projectname}, context)

def addedit_inf(request):
    InfFormSet = modelformset_factory(m.InflationIndices,form=InflationForm,extra=20)
    context = RequestContext(request)
    project_id = request.session['project_id']   
    setrec = m.Settings.objects.get(projectId=project_id)
    qset = m.InflationIndices.objects.filter(projectId=project_id)
    oldRecId = 0
    oldYear = 0
    result = 0
    for q in qset:
       if int(q.yearCPI) == setrec.yearEstimates: 
          oldRecId = q.id
          oldYear = q.yearCPI

    if request.method == 'POST':
       infform = InfFormSet(request.POST,request.FILES,prefix="infform")
       count = 0 
       if infform.is_valid():
          frm = infform.save(commit=False)
          for i in frm:
             if i.id == oldRecId:
                if i.yearCPI != oldYear:
                   count = 1
          for i in frm:
             if count != 1: 
                i.projectId = project_id  
                i.save()
                if i.id == oldRecId: 
                   result = calculations(project_id)
             else:
                return render_to_response ('project/inflation.html',{'infform':infform,'errtext': 'You cannot delete the inflation index for the year you selected in Project Settings.'},context) 
          return HttpResponseRedirect('/project/indices.html')
       else:
          form_errors = infform.errors
          return render_to_response ('project/inflation.html',{'infform':infform,'form.errors': form_errors},context)
    else:
        qset = m.InflationIndices.objects.filter(projectId=project_id)
        infform = InfFormSet(queryset=qset,prefix="infform")
    return render_to_response ('project/inflation.html',{'infform':infform},context)

def restore_inf(request):
    context = RequestContext(request)
    project_id = request.session['project_id']
    result = 0
    m.InflationIndices.objects.all().delete()
    for e in m.InflationIndices_orig.objects.all():
        m.InflationIndices.objects.create(yearCPI = e.yearCPI,indexCPI = e.indexCPI, projectId=project_id)
    result = calculations(project_id)
    return HttpResponseRedirect('/project/inflation.html')

def addedit_geo(request):
    GeoFormSet = modelformset_factory(m.GeographicalIndices,form=GeographicalForm,extra=20)
    context = RequestContext(request)

    if request.method == 'POST':
       geoform = GeoFormSet(request.POST,request.FILES)

       if geoform.is_valid():
          geoform.save()
          return HttpResponseRedirect('/project/indices.html')
       else:
          form_errors = geoform.errors
          return render_to_response ('project/geo.html',{'geoform':geoform,'form.errors': form_errors},context)
    else:
        geoform = GeoFormSet()

    return render_to_response ('project/geo.html',{'geoform':geoform},context) 

def restore_geo(request):
    context = RequestContext(request)
    m.GeographicalIndices.objects.all().delete()
    for e in m.GeographicalIndices_orig.objects.all():
        m.GeographicalIndices.objects.create(stateIndex = e.stateIndex,areaIndex = e.areaIndex, geoIndex = e.geoIndex )
    return HttpResponseRedirect('/project/geo.html')
