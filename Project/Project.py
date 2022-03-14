#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 16 14:50:19 2022

@author: albertsmith
"""

import os
import numpy as np
from pyDR.IO import read_file, readNMR, isbinary
from pyDR import Defaults
from pyDR import clsDict
import re
from copy import copy
from matplotlib.figure import Figure
ME=Defaults['max_elements']
decode=bytes.decode


class DataMngr():
    def __init__(self, project):
        self.project = project
        if not(os.path.exists(self.directory)):
            os.mkdir(self.directory)
        self._saved_files = list()
        for fname in os.listdir(self.directory):
            if '.data' in fname:
                self._saved_files.append(fname)
        self._saved_files.sort()
        self.data_objs = [None for _ in self.saved_files]
        self._hashes = [None for _ in self.saved_files]

    @property
    def directory(self):
        return os.path.join(self.project.directory, 'data')
        
    @property
    def saved_files(self):
        return self._saved_files
                
    def load_data(self,filename=None,index=None):
        "Loads a saved file from the project directory"
        if filename is not None:
            assert filename in self.saved_files,"{} not found in project. Use 'append_data' for new data".format(filename)
            index=self.saved_files.index(filename)
        fullpath=os.path.join(self.directory,self.saved_files[index])
        self.data_objs[index]=read_file(fullpath,directory=self.project.directory)
        self._hashes[index]=self.data_objs[index]._hash
        self.data_objs[index].source.project=self.project
        
        
    def append_data(self,data):
        filename=None
        if isinstance(data,str):
            filename,data=data,None
        "Adds data to the project (either from file, set 'filename' or loaded data, set 'data')"
        if filename is not None:
            if not(os.path.exists(filename)):
                if os.path.exists(os.path.join(os.path.dirname(self.directory),filename)):  #Check in the project directory
                    filename=os.path.join(os.path.dirname(self.directory),filename) 
                    """Note that adding data from within the project/data directory is discouraged,
                    so we do not check that directory here.
                    """
            assert os.path.exists(filename),"{} does not exist".format(filename)
            data=read_file(filename,directory=self.project.directory) if isbinary(filename) else readNMR(filename)

        if data in self.data_objs:
            print("Data already in project (index={})".format(self.data_objs.index(data)))
            return
            
        self.data_objs.append(data)
        self._hashes.append(None)   #We only add the hash value if data is saved
        self._saved_files.append(None)
        self.data_objs[-1].source.project=self.project
        
        if self.project is not None:
            flds=['Type','status','short_file','title','additional_info']
            dct={f:getattr(self.data_objs[-1].source,f) for f in flds}
            dct['filename']=None
            self.project.info.new_exper(**dct)
            self.project._index=np.append(self.project._index,len(self.data_objs)-1)
        
        if data.src_data is not None:
            if data.src_data in self.data_objs:
                data.src_data=self[self.data_objs.index(data.src_data)]
            else:
                self.append_data(data=data.src_data) #Recursively append source data
    
    def remove_data(self,index,delete=False):
        """
        Remove a data object from project. Set delete to True to also delete 
        saved data in the project folder. If delete is not set to True, saved 
        data will re-appear upon the next project load even if removed here.
        """
            
        if not(hasattr(index,'__len__')):
            self.data_objs.pop(index)
            self._hashes.pop(index)
            if delete and self.saved_files[index] is not None:
                os.remove(os.path.join(self.directory,self.saved_files[index]))
            self._saved_files.pop(index)
            self.project.info.del_exp(index)
        else:
            print(index)
            for i in np.sort(index)[::-1]:self.remove_data(i,delete=delete)
                
            
    
    def __getitem__(self,i):
        if hasattr(i,'__len__'):
            return [self[i0] for i0 in i]
        else:
            assert i<len(self.data_objs),"Index exceeds number of data objects in this project"
            if self.data_objs[i] is None:
                self.load_data(index=i)
            return self.data_objs[i]
            
    
    
    def __len__(self):
        return len(self.data_objs)
    
    def __iter__(self):
        def gen():
            for k in range(len(self)):
                yield self[k]
        return gen()
        
    @property
    def titles(self):
        return [d.title for d in self]
    
    @property
    def filenames(self):
        """
        List of filenames for previously saved data
        """
        return [d.source.saved_filename for d in self]
    
    @property
    def short_files(self):
        return [d.source.short_file for d in self]
    
    @property
    def save_name(self):
        """
        List of filenames used for saving data
        """
        names=list()
        for k,d in enumerate(self.data_objs):
            if d is None:
                name=self.saved_files[k]    #saved files can be shorter than d,
                                            #but I think d cannot be None for the latter values
            else:
                name=os.path.split(d.source.default_save_location)[1]
            if name in names:
                name=name[:-5]+'1'+name[-5:]
                k=2
                while name in names:
                    name=name[:-5]+'{}'.format(k)+name[-5:]
                    k+=1
            names.append(name)
        names=[os.path.join(self.directory,name) for name in names]
        return names
        
    @property
    def sens_list(self):
        return [d.sens for d in self]
    
    @property
    def detect_list(self):
        return [d.detect for d in self]
    
    @property
    def saved(self):
        "Logical index "
        return [True if d is None else h==d._hash for h,d in zip(self._hashes,self.data_objs)]
    
    def save(self,i='all'):
        """
        Save data object stored in the project by index, or set i to 'all' to
        save all data objects. Default is to derive the filename from the title.
        To save to a specific file, use data.save(filename='desired_name') instead
        of saving from the project.
        """
        if i=='all':
            for i in range(len(self)):
                if not(self.saved[i]):
                    if self[i].R.size>ME:
                        print('Skipping data object {0}. Size of data.R ({1}) exceeds default max elements ({2})'.format(i,self[i].R.size,ME))
                        continue
                    self.save(i)
        else:
            assert i<len(self),"Index {0} to large for project with {1} data objects".format(i,len(self))
            if not(self.saved[i]):
                src_fname=None
                if self[i].src_data is not None and not(isinstance(self[i].src_data,str)):
                    k=np.argwhere([self[i].src_data==d for d in self.data_objs])[0,0]
                    
                    if self[k].R.size<=ME:
                        self.save(k)
                    else:
                        print('Skipping source data of object {0} (project index {1}). Size of source data exceeds default max elements ({2})'.format(i,k,ME))
                    src_fname=self.save_name[k]
                self[i].save(self.save_name[i],overwrite=True,save_src=False,src_fname=src_fname)
                self[i].source.saved_filename=self.save_name[i]
                self._hashes[i]=self[i]._hash #Update the hash so we know this state of the data is saved
                self._saved_files[i]=self.save_name[i]
                self.project.info['filename',np.argwhere(self.project._index==i)[0,0]]=os.path.split(self.save_name[i])[1]
          

class DataSub(DataMngr):
    """
    Data storage object used for creating a sub-project of the given project.
    Removes various functionality of the main class.
    """
    def __init__(self, project, *data):
        assert not project.subproject,'Sub-project data objects should reference the parent project'
        self.project = project #This should be the parent project, not the subproject
        self.data_objs = data
        self._hashes = None
    "De-activated functions/properties below"
    @property
    def saved_files(self):
        pass
    def load_data(self, *args, **kwargs):
        pass
    def append_data(self, *args, **kwargs):
        pass
    def remove_data(self, *args, **kwargs):
        pass
    @property
    def saved(self):
        pass
    def save(self,*args,**kwargs):
        pass
    
    
    

            

#%% Detector Manager
class DetectMngr():
    def __init__(self,project):
        self.project=project

    def __iter__(self):
        r=self.detectors
        def gen():
            for r0 in r:
                yield r0
        return gen()

    @property
    def detectors(self):
        r=list()
        for d in self.project:
            if not(any([r0 is d.detect for r0 in r])):
                r.append(d.detect)
        return r
        
    def unify_detect(self, chk_sens_only: bool = False) ->None:
        """
        Checks for equality among the detector objects and assigns all equal
        detectors to the same object. This allows one to only optimize one of
        the data object's detectors, and all other objects with equal detectors
        will automatically match (also saves memory)
        
        Note that by default, if two detector objects based on matching 
        sensitivity 

        Parameters
        ----------
        chk_sens_only : bool, optional
            If two detector objects have matching input sensitivities, but have
            been optimized differently, they will not be considered equal, unless
            this flag is set to True. The default is False.

        Returns
        -------
        None

        """
        proj=self.project
        r=[d.detect for d in proj]
        s=[r0.sens for r0 in r]
        
        for k,(s0,r0) in enumerate(zip(s,r)):
            i=None
            if chk_sens_only:
                if s0 in s[:k]:
                    i=s[:k].index(s0)
            else:
                if r0 in r[:k]:
                    i=r[:k].index(r0)
            if i is not None:
                proj[k].sens=s[i]
                proj[k].detect=r[i]
                
    def unique_detect(self, index: int = None) -> None:
        project=self.project
        if index is None:
            for i in range(len(project.data)):
                self.unique_detect(i)
        else:
            d = project.data[index]
            sens = d.detect.sens
            d.detect = d.detect.copy()
            d.detect.sens = sens
    
    def r_auto(self,n:int,Normalization:str='MP',NegAllow:bool=False) -> None:
        """
        Finds the n optimal detector sensitivites for all data objects in the
        current subproject.

        Parameters
        ----------
        n : int
            Number of detector sensitivities to optimize.
        Normalization : str, optional
            Type of normalization used for optimization.
            'MP': Equal maxima, where if S2 is included, rho0 is positive
            'M': Equal maxima, where the sum of detector sensitivities is 1
                 -'M' and 'MP' are the same if S2 not used
            'I': Equal integrals
            The default is 'MP'.
        NegAllow : bool, optional
            Allow detector sensitivities to oscillate below zero. 
            The default is False.

        Returns
        -------
        None

        """
        self.unify_detect(chk_sens_only=True)
        for r in self:r.r_auto(n,Normalization=Normalization,NegAllow=NegAllow)
        
    def r_target(self,target:np.ndarray,n:int=None) -> None:
        """
        Optimizes detector sensitivities to some target function for all data
        objects in the current subproject.

        Parameters
        ----------
        target : np.ndarray
            numpy array with NxM elements. N is the number of detector sensitivities
            to match, and M is the number of correlation times stored in the
            sensitivity objects (default is 200)
        n : int, optional
            Number of singular values to use to match to the target function.
            By default, n gets set to N (see above), but often the reproduction
            of experimental sensitivities requires a larger value
            The default is None.

        Returns
        -------
        None

        """
        self.unify_detect(chk_sens_only=True)
        for r in self:r.r_target(target,n=n)
    
    def inclS2(self):
        """
        Include S2 in analysis (NMR experiments only!)

        Returns
        -------
        None.

        """
        for r in self:r.inclS2()
    
    def r_no_opt(self,n:int) -> None:
        """
        Optimize n detectors for pre-processing, i.e. with the no_opt setting

        Parameters
        ----------
        n : int
            Number of detectors to use.

        Returns
        -------
        None

        """
        self.unify_detect(chk_sens_only=True)
        for r in self:r.r_no_opt(n)
    
    def r_zmax(self,zmax,Normalization:str='MP',NegAllow:bool=False) -> None:
        """
        Optimize n detectors with maxima located at the positions given in zmax.

        Parameters
        ----------
        zmax : list,np.ndarray
            List of the target maxima for n detectors (n is the length of zmax).
        Normalization : str, optional
            Type of normalization used for optimization.
            'MP': Equal maxima, where if S2 is included, rho0 is positive
            'M': Equal maxima, where the sum of detector sensitivities is 1
                 -'M' and 'MP' are the same if S2 not used
            'I': Equal integrals
            The default is 'MP'.
        NegAllow : bool, optional
            Allow detector sensitivities to oscillate below zero. 
            The default is False.

        Returns
        -------
        None

        """
        self.unify_detect(chk_sens_only=True)
        for r in self:r.r_zmax(zmax,Normalization=Normalization,NegAllow=NegAllow)

    
#%% Project class
class Project():
    """
    Project class of pyDIFRATE, used for organizing data and plots
    """
    def __init__(self, directory:str, create:bool = False, subproject:bool = False) -> None:
        """
        Initialize a pyDIFRATE project, for organizing data and plots

        Parameters
        ----------
        directory : str
            Path to an existing or new project.
        create : bool, optional
            Create a new directory on the specified path if one does not exist.
            The default is False.
        subproject : bool, optional
            Set to True if this project is a subproject of another project. 
            Only intended for internal use. The default is False.

        Returns
        -------
        None

        """
        self.name = directory   #todo maybe create the name otherwise?
        self._directory = os.path.abspath(directory)
        if not(os.path.exists(self.directory)) and create:
            os.mkdir(self.directory)
        assert os.path.exists(self.directory),'Project directory does not exist. Select an existing directory or set create=True'
               
        self.data=DataMngr(self)
        self._subproject = subproject  #Subprojects cannot be edited/saved
        self.plots = [None]
        self._current_plot = [0]
        
        self.read_proj()
    
    @property
    def directory(self):
        return self._directory
    #%% setattr        
    def __setattr__(self,name,value):
        if name=='current_plot':
            self._current_plot[0]=value
            if value:
                while len(self.plots)<value:
                    self.plots.append(None)
                if self.plots[value-1] is None:
                    self.plots[value-1]=clsDict['DataPlots']()
                    self.plots[value-1].project=self
            return
        super().__setattr__(name,value)
    #%% Detector manager
    @property
    def detect(self):
        return DetectMngr(self)
    #%% Read/write project file
    def read_proj(self):
        info=clsDict['Info']()
        flds=['Type','status','short_file','title','additional_info','filename']
        for f in flds:info.new_parameter(f)
        
        if os.path.exists(os.path.join(self.directory,'project.txt')):
            dct={}
            with open(os.path.join(self.directory,'project.txt'),'r') as f:
                for line in f:
                    if line.strip()=='DATA':    #Start reading a new data entry
                        if len(dct):
                            info.new_exper(**dct)    #Store the previous entry if exists
                        dct={}  #Reset entry
                        for l in f:     #Sweep until the end of this entry
                            if l.strip()=='END:DATA':break   #End of entry reached
                            if len(l.split(':\t'))==2:
                                k,v=[l0.strip() for l0 in l.strip().split(':\t')]
                                if k in flds:dct[k]=v #Add this field to dct
                if len(dct):info.new_exper(**dct)    #Store the current entry
                
        for k,file in enumerate(self.data.saved_files):
            if file not in info['filename']:   #Also include data that might be missing from the project file
                src=self.data[k].source
                dct={f:getattr(src,f) for f in flds}
                dct['filename']=file
                info.new_exper(**dct)
                print(file)
        
        self._index=list()
        for file in info['filename']:
            if file in self.data.saved_files:
                self._index.append(self.data.saved_files.index(file))
            else:
                self._index.append(None)
                print('File:\n{0}\n was missing from project'.format(file))
        
        while None in self._index: #Delete all missing data
            i=self._index.index(None)
            self._index.pop(i)

        self.info=clsDict['Info']()
        for k in range(len(self._index)):
            self.info.new_exper(**info[self._index.index(k)])
        self._index=np.array(self._index,dtype=int)
                
    def write_proj(self):
        with open(os.path.join(self.directory,'project.txt'),'w') as f:
            for i in self._index:
                f.write('DATA\n')
                for k,v in self.info[i].items():f.write('{0}:\t{1}\n'.format(k,v))
                f.write('END:DATA\n')

    #%%Indexing/subprojects
    @property
    def subproject(self):
        return self._subproject
    
    def append_data(self,data):
        assert not(self._subproject),"Data cannot be appended to subprojects"
        self.data.append_data(data)
        
    def remove_data(self,index,delete=False):
        #TODO implement this the right way
        assert not(self._subproject),"Data cannot be removed from subprojects"
        proj=self[index]
        
        if hasattr(proj,'R'):#Single index given, thus self[index] returns a data object
            index=[self.data.data_objs.index(proj)]
        else:
            index=np.sort(proj._index)[::-1]
        
        # if delete and len(index)>1:
        #     print('Delete data sets permanently by full title or index (no multi-delete of saved data allowed)')
        #     return
        
        for i in index:
            self.data.remove_data(index=i,delete=delete)
            self._index=self._index[self._index!=i]
            self._index[self._index>i]-=1

    def __iter__(self):
        def gen():
            for k in self._index:
                yield self.data[k]
        return gen()
    
    def __len__(self) -> int:
        return self._index.size


    @property
    def size(self) -> int:
        return self.__len__()
    
    def __getitem__(self, index: int):
        """
        Extract a data object or objects by index or title (returns one item) or
        by Type or status (returns a list).
        """
        if isinstance(index, int): #Just return the data object
            assert index < self.__len__(), "index too large for project of length {}".format(self.__len__())
            return self.data[self._index[index]]
        
        
        proj=copy(self)
        proj._subproject=True
        if isinstance(index,str):
            flds=['Types','statuses','additional_info','titles','short_files']
            for f in flds:
                if index in getattr(self,f):
                    proj._index=self._index[getattr(self,f)==index]
                    return proj
            r = re.compile(index)
            i=list()
            for t in self.titles:
                i.append(True if r.match(t) else False)
                
            proj._index=self._index[np.array(i)]
        elif hasattr(index,'__len__'):
            proj._index=self._index[index]
        elif isinstance(index,slice):
            start = 0 if index.start is None else index.start
            step = 1 if index.step is None else index.step
            stop = self.size if index.stop is None else min(index.stop, self.size)
            start %= self.size
            stop = (stop-1) % self.size+1
            if step<0:start,stop=stop-1,start-1
            proj._index = self._index[np.arange(start,stop,step)]
            if len(proj._index):
                return proj
        else:
            print('index was not understood')
            return
        return proj
        
        
        
    @property
    def Types(self):
        return self.info['Type'][self._index]
    
    @property
    def statuses(self):
        return self.info['status'][self._index]
    
    @property
    def titles(self): 
        return self.info['title'][self._index]
    
    @property
    def short_files(self):
        return self.info['short_file'][self._index]
    
    @property
    def additional_info(self):
        return self.info['additional_info'][self._index]
    
    def save(self):
        assert not(self._subproject),"Sub-projects cannot be saved"
        self.data.save()
        self.write_proj()
    
    
    #%% Plotting functions
    @property
    def plot_obj(self):
        """
        Returns the current DataPlots object.

        Returns
        -------
        DataPlots
            DESCRIPTION.

        """
        if self.current_plot:
            return self.plots[self.current_plot-1]
    
    @property
    def fig(self) -> Figure:
        """
        Returns the current matplotlib Figure

        Returns
        -------
        Figure

        """
        if self.current_plot:
            return self.plot_obj.fig
    
    def savefig(self,fignum:int=None,filename:str=None,filetype:str='png',overwrite:bool=False) -> None:
        """
        Saves a figure from the project into the project's figure folder.
        
        Parameters
        ----------
        fignum : int, optional
            Index of the figure in the project (1 or higher). Defaults to the
            current figure if not provided. The default is None.
        filename : str, optional
            Filename for the figure. Defaults to the window title if not 
            provided. Provide an absolute path to save outside of the project 
            folder.
            The default is None.
        overwrite : bool, optional
            Overwrite existing figures. The default is False.

        Returns
        -------
        None

        """
        if not(os.path.exists(os.path.join(self.directory,'figures'))):
            os.mkdir(os.path.join(self.directory,'figures'))
            
        if fignum is None:fignum=self.current_plot
        assert self.plots[fignum-1] is not None,"Selected figure ({}) does not exist".format(fignum)
        if filename is None:filename=self.plots[fignum-1].fig.canvas.get_window_title()
        for s in [' ','.','%','&','{','}','/','<','>','*','?','/','$','!',"'",'"',':','@','+','`','|','=']:
            # filename=filename.replace(s,'' if s in [',','.','"',"'"] else '_')
            filename=filename.replace(s,'_')
            while '__' in filename:filename=filename.replace('__','_')
        if filetype[0]=='.':filetype=filetype[1:]
        if filename[-4]!='.':filename+='.'+filetype
        
        filename=os.path.join(os.path.join(self.directory,'figures'),filename)
        self.plots[fignum-1].fig.savefig(filename)
        
    @property
    def current_plot(self):
        if self._current_plot[0]>len(self.plots):self._current_plot[0]=len(self.plots)
        return self._current_plot[0]
    
    def close_fig(self, fig):
        """
        Closes a figure of the project

        Parameters
        ----------
        plt_num : int
            Clears and closes a figure in the project. Provide the index 
            (ignores indices corresponding to non-existant figures)

        Returns
        -------
        None.

        """
        if isinstance(fig,str) and fig.lower()=='all':
            for i in range(len(self.plots)):self.close_fig(i)
            return
        fig-=1
        if len(self.plots) > fig and self.plots[fig] is not None:
            self.plots[fig].close()
            self.plots[fig] = None
        
    def plot(self, data_index=None, data=None, fig=None, style='plot',
                  errorbars=False, index=None, rho_index=None, split=True, plot_sens=True, title=None, **kwargs):
        """
        

        Parameters
        ----------
        data : pyDR.Data, optional
            data object to be plotted. The default is None.
        data_index : int, optional
            index to determine which data object in the project to plot. The default is None.
        fig : int, optional
            index to determine which plot to use. The default is None (goes to current plot).
        style : str, optional
            'p', 's', or 'b' specifies a line plot, scatter plot, or bar plot. The default is 'plot'.
        errorbars : bool, optional
            Show error bars (True/False). The default is True.
        index : int/bool array, optional
            Index to determine which residues to plot. The default is None (all residues).
        rho_index : int/bool array, optional
            index to determine which detectors to plot. The default is None (all detectors).
        split : bool, optional
            Split line plots with discontinuous x-data. The default is True.
        plot_sens : bool, optional
            Show the sensitivity of the detectors in the top plot (True/False). The default is True.
        **kwargs : TYPE
            Various arguments that are passed to matplotlib.pyplot for plotting (color, linestyle, etc.).

        Returns
        -------
        DataPlots object

        """
        if fig is None:fig=self.current_plot if self.current_plot else 1
        self.current_plot=fig
        if title:self.fig.canvas.set_window_title(title)
        
        if data is None and data_index is None: #Plot everything in project
            if self.size:
                for i in range(self.size):
                    out=self.plot(data_index=i,style=style,errorbars=errorbars,index=index,
                             rho_index=rho_index,plot_sens=plot_sens,split=split,fig=fig,**kwargs)
                return out
            return
        
        
        if data is None:
            data = self[data_index]
        # if self.plots[fig-1] is None:
        #     self.plots[fig-1] = clsDict['DataPlots'](data=data, style=style, errorbars=errorbars, index=index,
        #                  rho_index=rho_index, plot_sens=plot_sens, split=split, **kwargs)
        #     self.plots[fig].project=self
        # else:
            
        self.plots[fig-1].append_data(data=data,style=style,errorbars=errorbars,index=index,
                     rho_index=rho_index,plot_sens=plot_sens,split=split,**kwargs)
        return self.plots[fig-1]

    def comparable(self, i: int, threshold: float = 0.9, mode: str = 'auto', min_match: int = 2) -> tuple:
        """
        Find objects that are recommended for comparison to a given object. 
        Provide either an index (i) referencing the data object's position in 
        the project or by providing the object itself. An index will be
        returned, corresponding to the data objects that should be compared to
        the given object
        
        Comparability is defined as:
            1) Having some selections in common. This is determined by running 
                self[k].source.select.compare(i,mode=mode)
            2) Having 
                a) Equal sensitivities (faster calculation, performed first)
                b) overlap of the object sensitivities above some threshold.
                This is defined by sens.overlap_index, where we require 
                at least min_match elements in the overlap_index (default=2)
        """

        #todo argument mode is never used?

        if isinstance(i, int):
            i = self[i] #Get the corresponding data object
        out = list()
        for s in self:
            if s.select.compare(i.select)[0].__len__() == 0:
                out.append(False)
                continue
            out.append(s.sens.overlap_index(i.sens, threshold=threshold)[0].__len__() >= min_match)
        return np.argwhere(out)[:, 0]
                    
    


    #%% Fitting functions
    def opt2dist(self, rhoz_cleanup=False, parallel=False) -> None:
        """
        Optimize fits to match a distribution for all detectors in the project.
        """
        sens = list()
        detect = list()
        count = 0
        for d in self:
            if hasattr(d.sens,'opt_pars') and 'n' in d.sens.opt_pars:
                fit = d.opt2dist(rhoz_cleanup, parallel=parallel)
                if fit is not None:
                    count += 1
                    if fit.sens in sens:
                        i = sens.index(fit.sens)
                        fit.sens = sens[i]
                        fit.detect = detect[i]
                    else:
                        sens.append(fit.sens)
                        detect.append(clsDict['Detector'](fit.sens))
        print('Optimized {0} data objects'.format(count))
    
    def fit(self, bounds: bool = True, parallel: bool = False) -> None:
        """
        Fit all data in the project that has optimized detectors.
        """
        sens = list()
        detect = list()
        count = 0
        for d in self:
            if 'n' in d.detect.opt_pars:
                count += 1
                fit = d.fit(bounds=bounds, parallel=parallel)
                if fit.sens in sens:
                    i = sens.index(fit.sens)    #We're making sure not to have copies of identical sensitivities and detectors
                    fit.sens = sens[i]
                    fit.detect = detect[i]
                else:
                    sens.append(fit.sens)
                    detect.append(fit.detect)
        print('Fitted {0} data objects'.format(count))

    #%% iPython stuff   
    def _ipython_display_(self):
        print("pyDIFRATE project with {0} data sets\n{1}\n".format(self.size,super().__repr__()))
        print('Titles:')
        for t in self.titles:print(t)
        
    def _ipython_key_completions_(self) -> list:
        out = list()
        for k in ['Types', 'statuses', 'additional_info', 'titles']:
            for v in getattr(self, k):
                if v not in out:
                    out.append(v)
        return out
 



       








