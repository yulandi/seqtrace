#!/usr/bin/python
# Copyright (C) 2018 Brian J. Stucky
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GdkPixbuf

import sys
import os.path

from seqtrace.core import sequencetrace
from seqtrace.core.consens import ConsensSeqBuilder, ModifiableConsensSeqBuilder
from seqtrace.core.stproject import SequenceTraceProject
from seqtrace.core import stproject_io
from seqtrace.core import seqwriter
from seqtrace.core.consens import ConsensSeqSettings

import seqtrace.gui.dialgs as dialgs
from seqtrace.gui.dialgs import CommonDialogs, EntryDialog, ProgressBarDialog
from seqtrace.gui.statusbar import ProjectStatusBar
from seqtrace.gui.projsettingsdialg import ProjectSettingsDialog
from seqtrace.gui.tracewindow_mgr import TraceWindowManager
from seqtrace.gui.projviewer import ProjectViewer

# Get the location of the GUI image files.
from seqtrace.gui import images_folder


class MainWindow(Gtk.Window, CommonDialogs):
    def __init__(self):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.project = SequenceTraceProject()
        self.project_open = False

        self.tw_manager = TraceWindowManager()

        self.fextension = '.str'
        self.wintitle = 'SeqTrace'
        self.project.registerObserver(
            'save_state_change', self.projSaveStateChanged
        )
        self.project.registerObserver(
            'project_filename_change', self.projFilenameChanged
        )
        self.project.getConsensSeqSettings().registerObserver(
            'settings_change', self.consSeqSettingsChanged
        )

        # initialize the window GUI elements
        self.connect('delete-event', self.deleteEvent)
        self.vbox = Gtk.VBox(False, 0)
        self.add(self.vbox)

        # create the menus and toolbar
        menuxml = '''<menubar name="menubar">
        <menu action="File">
            <menuitem action="Open" />
            <menuitem action="New" />
            <menuitem action="Close" />
            <separator />
            <menuitem action="Save" />
            <menuitem action="Save_As" />
            <separator />
            <menuitem action="Revert_To_Saved" />
            <separator />
            <menuitem action="Open_Trace" />
            <separator />
            <menuitem action="Project_Settings" />
            <separator />
            <menuitem action="Exit" />
        </menu>
        <menu action="Trace_Files">
            <menuitem action="View_File" />
            <separator />
            <menuitem action="Add_File" />
            <menuitem action="Remove_File" />
            <separator />
            <menuitem action="Find_FwdRev" />
            <separator />
            <menuitem action="Associate_Files" />
            <menuitem action="Dissociate_Files" />
            <menu action="Auto_Associate">
                <menuitem action="Auto_Associate_All" />
                <menuitem action="Auto_Associate_Selected" />
            </menu>
            <separator />
            <menuitem action="View_Expand_All" />
            <menuitem action="View_Collapse_All" />
        </menu>
        <menu action="Sequences">
            <menu action="Export">
                <menuitem action="Export_Selected" />
                <menuitem action="Export_All" />
            </menu>
            <separator />
            <menu action="Generate">
                <menuitem action="Generate_Selected" />
                <menuitem action="Generate_All" />
            </menu>
            <separator />
            <menu action="Delete">
                <menuitem action="Delete_Sel_Seqs" />
                <menuitem action="Delete_All_Seqs" />
            </menu>
        </menu>
        <menu action="Help">
            <menuitem action="About" />
        </menu></menubar>
        <popup name="projview_popup">
            <menuitem action="Popup_Rename_Row" />
            <menuitem action="Popup_Edit_Notes" />
            <separator />
            <menuitem action="Dissociate_Files" />
            <separator />
            <menuitem action="Popup_Remove_File" />
            <separator />
            <menuitem action="Popup_Delete_Sel_Seqs" />
        </popup>
        <toolbar name="toolbar">
            <toolitem action="Open" />
            <toolitem action="New" />
            <toolitem action="Save" />
            <separator />
            <toolitem action="Project_Settings" />
            <separator />
            <toolitem action="View_File" />
            <toolitem action="Add_File" />
            <separator />
            <toolitem action="Export_All" />
        </toolbar>'''
        # These actions are always enabled.
        self.main_ag = Gtk.ActionGroup('main_actions')
        self.main_ag.add_actions([
            ('File', None, '_File'),
            ('Open', Gtk.STOCK_OPEN, '_Open project...', None, 'Open a project file', self.openProjectAction),
            ('New', Gtk.STOCK_NEW, '_New project...', None, 'Create a new project', self.newProject),
            ('Open_Trace', None, 'Open _trace file...', None, 'Open a trace file without adding it to the current project',
                self.actionOpenTraceFile),
            ('Exit', Gtk.STOCK_QUIT, 'E_xit', None, 'Exit the program', self.deleteEvent),
            ('Sequences', None, '_Sequences'),
            ('Trace_Files', None, '_Traces'),
            ('Help', None, '_Help'),
            ('About', Gtk.STOCK_ABOUT, '_About...', None, 'Display information about this program', self.showAbout)])

        # These actions are generally only enabled when a project is open.
        self.main_proj_ag = Gtk.ActionGroup('project_actions')
        self.main_proj_ag.add_actions([
            ('Close', Gtk.STOCK_CLOSE, '_Close project', None, 'Close the current project', self.closeProject),
            ('Save', Gtk.STOCK_SAVE, '_Save project', None, 'Save the current project', self.saveProject),
            ('Save_As', Gtk.STOCK_SAVE_AS, '_Save project as...', None, 'Save as a new project', self.saveProjectAs),
            ('Revert_To_Saved', Gtk.STOCK_REVERT_TO_SAVED, '_Reload project', None,
                'Reload the project from the last saved version', self.revertToSaved),
            ('Export', Gtk.STOCK_CONVERT, '_Export sequences', None, 'Export sequences to a file'),
            ('Export_All', Gtk.STOCK_CONVERT, 'From _all trace files...', None, 'Export all in-use sequences', self.exportAll),
            ('Delete', None, '_Delete saved sequences', None),
            ('Delete_All_Seqs', None, 'For _all trace files', None, 'Deleted all saved sequences', self.deleteAllSeqs),
            ('Project_Settings', Gtk.STOCK_PREFERENCES, '_Project Settings...', None,
                'View and change the settings for the current project', self.projectSettings),
            ('Add_File', Gtk.STOCK_ADD, '_Add trace file(s)...', None, 'Add trace files to the project', self.projectAddFiles),
            ('Auto_Associate', None, '_Auto-group trace files'),
            ('Auto_Associate_All', None, 'Auto-group all trace files', None,
                'Automatically recognize and group forward/reverse trace files', self.projectAssociateAllFiles),
            ('View_Expand_All', None, 'Expand all groups', None,
                'Expand the view of all forward/reverse groups', lambda widget: self.projview.expandAll()),
            ('View_Collapse_All', None, 'Collapse all groups', None,
                'Collapse the view of all forward/reverse groups', lambda widget: self.projview.collapseAll()),
            ('Generate', None, '_Generate finished sequences'),
            ('Generate_All', None, 'For _all trace files', None, 'Calculated finished sequences for all trace files',
                self.generateAllSequences)
            ])

        # These actions are only enabled when one or more trace files in the
        # project are selected.
        self.sel_proj_ag = Gtk.ActionGroup('project_actions_selected')
        self.sel_proj_ag.add_actions([
            ('Export_Selected', None, 'From _selected trace files...', None, 'Export all selected in-use sequences',
                self.exportSelected),
            ('Delete_Sel_Seqs', None, 'For _selected trace files', None, 'Deleted all saved sequences in selection',
                self.deleteSelSeqs),
            ('View_File', Gtk.STOCK_FIND, '_View selected trace file(s)...', None, 'View the selected trace file(s)',
                self.projectViewFiles),
            ('Remove_File', Gtk.STOCK_DELETE, '_Remove selected trace file(s)', None,
                'Remove the selected trace file(s) from the project', self.projectRemoveFiles),
            ('Find_FwdRev', None, '_Find and mark forward/reverse', None,
                'Identify the selected trace files as forward or reverse reads, if possible', self.findFwdRev),
            ('Associate_Files', None, '_Group selected forward/reverse files', None,
                'Associate the selected trace files as complementary forward/reverse traces', self.projectAssociateFiles),
            ('Dissociate_Files', None, '_Ungroup forward/reverse files', None,
                'Remove the selected forward/reverse trace file associations', self.projectDissociateFiles),
            ('Auto_Associate_Selected', None, 'Auto-group selected trace files', None,
                'Automatically recognize and group forward/reverse trace files', self.projectAssociateSelectedFiles),
            ('Generate_Selected', None, 'For _selected trace files', None, 'Calculated finished sequences for selected trace files',
                self.generateSelectedSequences)
            ])

        # These actions are specific to the project viewer context popup menu.
        self.popup_proj_ag = Gtk.ActionGroup('project_actions_popup')
        self.popup_proj_ag.add_actions([
            ('Popup_Remove_File', Gtk.STOCK_REMOVE, '_Remove trace file', None, 'Remove the selected trace file from the project',
                self.projectRemoveFiles),
            ('Popup_Delete_Sel_Seqs', None, 'Delete saved sequence', None, 'Deleted the saved consensus sequence', self.deleteSelSeqs),
            ('Popup_Rename_Row', None, 'Rename', None, 'Rename the forward/reverse group', self.popupRenameRow),
            ('Popup_Edit_Notes', Gtk.STOCK_EDIT, 'Edit notes', None, 'Edit the notes/description for this item', self.popupEditNotes)
            ])

        # build the UIManager
        self.uim = Gtk.UIManager()
        self.add_accel_group(self.uim.get_accel_group())
        self.uim.insert_action_group(self.main_ag)
        self.uim.insert_action_group(self.main_proj_ag)
        self.uim.insert_action_group(self.sel_proj_ag)
        self.uim.insert_action_group(self.popup_proj_ag)
        self.uim.add_ui_from_string(menuxml)

        # add the menu bar to the window
        self.vbox.pack_start(self.uim.get_widget('/menubar'), False, False, 0)

        # set the toolbar appearance and add it to the window
        self.uim.get_widget('/toolbar').set_icon_size(Gtk.IconSize.LARGE_TOOLBAR)
        self.uim.get_widget('/toolbar').set_style(Gtk.ToolbarStyle.ICONS)
        self.vbox.pack_start(self.uim.get_widget('/toolbar'), False, False, 0)

        # disable the project-specific menus/toolbar buttons by default
        self.main_proj_ag.set_sensitive(False)
        self.sel_proj_ag.set_sensitive(False)

        # initialize the project viewer
        self.projview = ProjectViewer(self.project)
        self.projview.registerObserver('selection_changed', self.projViewSelectChanged)
        self.projview.registerObserver('right_clicked', self.projViewRightClicked)
        self.projview.registerObserver('isfwdrew_clicked', self.projViewIsfwdrevClicked)
        self.projview.registerObserver('item_renamed', self.projViewNameEdited)
        self.projview.registerObserver('notes_edited', self.projViewNotesEdited)
        self.projview.registerObserver('useseq_changed', self.projViewUseseqChanged)
        self.view_has_selection = False
        self.vbox.pack_start(self.projview, True, True, 0)

        # add a status bar for the project
        self.statusbar = ProjectStatusBar(self.project)
        self.vbox.pack_start(self.statusbar, False, True, 0)

        self.vbox.show_all()
        self.vbox.show()
        self.set_title(self.wintitle)

        self.setDefaultGeometry()

        # Set the initial window position to the top left corner of the desktop to allow easier use
        # with open trace windows.
        # There is a bit of platform-specific code here.  On Windows, move() only seems to work after
        # show() has already been called.  On GNU/Linux, calling move() after calling show() can cause
        # the window to interfere with the desktop panel (in XFCE, at least), so it appears to work best
        # to call move() prior to calling show().
        if not(sys.platform.startswith('win')):
            self.move(0, 0)
            self.show()
        else:
            self.show()
            self.move(0, 0)

        self.set_focus(None)

    def setDefaultGeometry(self):
        screen = self.get_screen()

        # calculate the default height based on the screen size
        new_height = (screen.get_height() * 5) / 6
        new_width = 600

        if new_width > screen.get_width():
            new_width = screen.get_width()

        #self.resize(580, 520)
        self.set_default_size(new_width, new_height)

        #self.set_position(Gtk.WindowPosition.CENTER)

    def projSaveStateChanged(self, save_state):
        if save_state:
            self.main_proj_ag.get_action('Save').set_sensitive(False)
        else:
            self.main_proj_ag.get_action('Save').set_sensitive(True)

    def projFilenameChanged(self, fname):
        self.set_title(os.path.basename(fname) + ' - ' + self.wintitle)

    def consSeqSettingsChanged(self):
        # if the project isn't empty, ask the user what to do with existing sequences
        if not(self.project.isProjectEmpty()):
            diag = Gtk.MessageDialog(
                self, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK, 'The settings for calculating consensus sequences have changed.  You might not want to use any previously saved consensus sequences.'
            )
            rb1 = Gtk.RadioButton(label='Mark all saved sequences as unused.')
            rb1.set_active(True)
            rb2 = Gtk.RadioButton(
                group=rb1, label='Delete all saved sequences.'
            )
            rb3 = Gtk.RadioButton(
                group=rb1, label='Do not make any changes to the project.'
            )

            rbbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            rbbox.set_margin_left(12)
            rbbox.pack_start(rb1, False, False, 0)
            rbbox.pack_start(rb2, False, False, 0)
            rbbox.pack_start(rb3, False, False, 0)
            diag.vbox.pack_start(rbbox, True, True, 0)

            diag.show_all()
            diag.run()

            if rb1.get_active():
                for item in self.project:
                    item.setUseSequence(False)
                    for child in item.getChildren():
                        child.setUseSequence(False)
            elif rb2.get_active():
                for item in self.project:
                    item.deleteConsensusSequence()
                    for child in item.getChildren():
                        child.deleteConsensusSequence()

            diag.destroy()

    def projectSettings(self, widget):
        sdiag = ProjectSettingsDialog(self, self.project)
        response = Gtk.ResponseType.OK
        settings_valid = False

        while (response == Gtk.ResponseType.OK) and not(settings_valid):
            response = sdiag.run()
            if response != Gtk.ResponseType.OK:
                break

            settings_valid = sdiag.checkSettingsValues()

        sdiag.hide()

        if response == Gtk.ResponseType.OK:
            sdiag.updateProjectSettings()

        sdiag.destroy()

    def popupRenameRow(self, widget):
        self.projview.requestEditSelectedRowName()

    def popupEditNotes(self, widget):
        self.projview.requestEditSelectedRowNotes()

    def projViewNameEdited(self, item, new_text):
        new_text = new_text.strip()
        if new_text == '':
            return

        item.setName(new_text)

    def projViewNotesEdited(self, item, new_text):
        new_text = new_text.strip()
        item.setNotes(new_text)

    def projViewRightClicked(self, item, event):
        # enable/disable popup menu items depending upon the selected row
        if item.isFile():
            self.uim.get_widget('/projview_popup/Popup_Remove_File').set_visible(True)
            self.uim.get_widget('/projview_popup/Dissociate_Files').set_visible(False)
            self.uim.get_widget('/projview_popup/Popup_Rename_Row').set_visible(False)
        else:
            self.uim.get_widget('/projview_popup/Popup_Remove_File').set_visible(False)
            self.uim.get_widget('/projview_popup/Dissociate_Files').set_visible(True)
            self.uim.get_widget('/projview_popup/Popup_Rename_Row').set_visible(True)

        if item.hasSequence():
            self.uim.get_widget('/projview_popup/Popup_Delete_Sel_Seqs').set_visible(True)
        else:
            self.uim.get_widget('/projview_popup/Popup_Delete_Sel_Seqs').set_visible(False)
            
        self.uim.get_widget('/projview_popup').popup(
            None, None, None, None, event.button, event.time
        )

    def projViewIsfwdrevClicked(self, item, event):
        if item.isFile():
            item.toggleIsReverse()

    def projViewUseseqChanged(self, item):
        if item.hasSequence():
            item.toggleUseSequence()
        else:
            self.showMessage('No consensus sequence has been saved for this trace file.  You must first view the sequencing trace, then save the consensus sequence from the trace.')

    def projViewSelectChanged(self, sel_cnt):
        if sel_cnt == 0:
            # Disable the selection-dependent UI elements.
            self.sel_proj_ag.set_sensitive(False)

            self.view_has_selection = False
        else:
            # Enable the selection-dependent UI elements, if needed.
            if not(self.view_has_selection):
                self.sel_proj_ag.set_sensitive(True)
                self.view_has_selection = True

            # Handle a few UI elements with more specific selection
            # requirements.

            assoc_files = self.sel_proj_ag.get_action('Associate_Files')
            enabled = False
            if sel_cnt == 2:
                # Make sure the selected items are both files.
                items = self.projview.getSelection()
                if items[0].isFile() and items[1].isFile():
                    enabled = True
            if enabled != assoc_files.get_sensitive():
                assoc_files.set_sensitive(enabled)

            auto_assoc = self.sel_proj_ag.get_action('Auto_Associate_Selected')
            enabled = False
            if sel_cnt >= 2:
                enabled = True
            if enabled != auto_assoc.get_sensitive():
                auto_assoc.set_sensitive(enabled)

            dissoc_files = self.sel_proj_ag.get_action('Dissociate_Files')
            enabled = False
            # Make sure at least one selected item is a group.
            items = self.projview.getSelection()
            for item in items:
                if not(item.isFile()):
                    enabled = True
                    break
            if enabled != dissoc_files.get_sensitive():
                dissoc_files.set_sensitive(enabled)

    def getFileExtension(self):
        return self.fextension

    def openProjectAction(self, widget):
        # create a file chooser dialog to get a file name from the user
        fc = Gtk.FileChooserDialog(
            'Open Project', self, Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_OPEN, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        )
        fc.set_current_folder(os.getcwd())

        f1 = Gtk.FileFilter()
        f1.set_name('project files')
        f1.add_pattern('*' + self.fextension)
        f2 = Gtk.FileFilter()
        f2.set_name('all files')
        f2.add_pattern('*')
        fc.add_filter(f1)
        fc.add_filter(f2)
        response = fc.run()
        fname = fc.get_filename()
        fc.destroy()
        if response != Gtk.ResponseType.OK:
            return

        # if a project is already open, try to close it first
        if self.project_open:
            if not(self.closeProject(None)):
                return

        self.openProject(fname)

    def openProject(self, fname):
        try:
            self.project.loadProjectFile(fname)
        except IOError:
            self.showMessage('The project file "' + fname + '" could not be opened.  Verify that the file exists and that you have permission to read it.')
            return
        except stproject_io.FileDataError:
            self.showMessage('The project file "' + fname + '" is corrupt or in an unrecognized format.')
            return
        except stproject_io.FileFormatVersionError:
            self.showMessage('The file format version of "' + fname + '" is not supported by this version of the software.')
            return

        self.main_proj_ag.set_sensitive(True)

        self.project_file = fname
        self.set_title(os.path.basename(fname) + ' - ' + self.wintitle)
        self.project_open = True

    def actionOpenTraceFile(self, widget):
        # create a file chooser dialog to get a file name from the user
        fc = Gtk.FileChooserDialog(
            'Open Trace File', self, Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_OPEN, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        )
        fc.set_current_folder(self.project.getTraceFileDir())
        f1 = Gtk.FileFilter()
        f1.set_name('trace files (*.ab1;*.scf;*.ztr)')
        f1.add_pattern('*.ztr')
        f1.add_pattern('*.ab1')
        f1.add_pattern('*.scf')
        f2 = Gtk.FileFilter()
        f2.set_name('all files (*)')
        f2.add_pattern('*')
        fc.add_filter(f1)
        fc.add_filter(f2)
        response = fc.run()
        fname = fc.get_filename()
        fc.destroy()
        if response != Gtk.ResponseType.OK:
            return

        self.openTraceFile(fname)

    def openTraceFile(self, filename):
        seqt = self.openTraceFileInternal(filename)
        if seqt == None:
            return

        settings = ConsensSeqSettings()

        # if a project is open, use the consensus settings from the project
        if self.project_open:
            settings.copyFrom(self.project.getConsensSeqSettings())

        csb = ModifiableConsensSeqBuilder((seqt,), settings)

        # create a new trace window
        newwin = self.tw_manager.newTraceWindow(csb)
        newwin.show()
        newwin.set_focus(None)

    def newProject(self, widget):
        # if a project is already open, try to close it first
        if self.project_open:
            if not(self.closeProject(None)):
                return

        self.project.clearProject()

        self.main_proj_ag.set_sensitive(True)

        self.project_open = True
        self.set_title('new project - ' + self.wintitle)

        # prompt the user to customize the settings for the new project
        self.projectSettings(None)

    def closeProject(self, widget, show_confirm=True):
        if not(self.project.getSaveState()) and show_confirm:
            # see if the user wants to save the project before closing it
            msg = 'Do you want to save the current project before closing it?  All unsaved changes will be lost.'
            response = self.showYesNoCancelDialog(msg)
            if response == Gtk.ResponseType.YES:
                saved = self.saveProject(None)
                if not(saved):
                    return False
            elif response != Gtk.ResponseType.NO:
                return False

        # close any project trace windows that are still open
        self.tw_manager.closeProjectTraceWindows()

        # clear all project data
        self.project.clearProject()

        self.main_proj_ag.set_sensitive(False)
        self.sel_proj_ag.set_sensitive(False)

        self.project_open = False
        self.statusbar.showNoProject()
        self.set_title(self.wintitle)

        return True

    def revertToSaved(self, widget):
        if not(self.project.getSaveState()):
            # make sure this is what the user actually wants to do
            response = self.showYesNoDialog('Are you sure you want to reload the current project?  All unsaved changes will be lost.')
            if response != Gtk.ResponseType.YES:
                return

        fname = self.project_file

        res = self.closeProject(None, False)
        if not(res):
            return

        self.openProject(fname)

    def saveProject(self, widget):
        # if the current project does not have a file name, prompt for one
        if self.project.getProjectFileName() == '':
            # create a file chooser dialog to get a file name from the user
            fc = Gtk.FileChooserDialog(
                'Save Project', self, Gtk.FileChooserAction.SAVE,
                (Gtk.STOCK_SAVE, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            )
            fc.set_current_folder(os.getcwd())
            fc.set_do_overwrite_confirmation(True)

            f1 = Gtk.FileFilter()
            f1.set_name('project files (*' + self.fextension + ')')
            f1.add_pattern('*' + self.fextension)
            f2 = Gtk.FileFilter()
            f2.set_name('all files (*)')
            f2.add_pattern('*')
            fc.add_filter(f1)
            fc.add_filter(f2)
            response = fc.run()
            fname = fc.get_filename()
            fc.destroy()
            if response != Gtk.ResponseType.OK:
                return False

            # make sure the file name has the correct extension
            if not(fname.endswith(self.fextension)):
                fname += self.fextension

            self.project.setProjectFileName(fname)

        try:
            self.project.saveProjectFile()
            return True
        except IOError:
            self.showMessage('Unable to save the project file "' + self.project.getProjectFileName()
                    + '".  Verify that you have permission to write to the specified file.')
            return False

    def saveProjectAs(self, widget):
        # create a file chooser dialog to get a file name from the user
        fc = Gtk.FileChooserDialog(
            'Save Project As', self, Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_SAVE, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        )
        fc.set_current_folder(os.getcwd())
        fc.set_do_overwrite_confirmation(True)

        f1 = Gtk.FileFilter()
        f1.set_name('project files (*' + self.fextension + ')')
        f1.add_pattern('*' + self.fextension)
        f2 = Gtk.FileFilter()
        f2.set_name('all files (*)')
        f2.add_pattern('*')
        fc.add_filter(f1)
        fc.add_filter(f2)
        response = fc.run()
        fname = fc.get_filename()
        fc.destroy()
        if response != Gtk.ResponseType.OK:
            return

        # make sure the file name has the correct extension
        if not(fname.endswith(self.fextension)):
            fname += self.fextension

        self.project.setProjectFileName(fname)

        try:
            self.project.saveProjectFile()
        except IOError:
            self.showMessage('Unable to save the project file "' + self.project.getProjectFileName()
                    + '".  Verify that you have permission to write to the specified file.')

    def exportAll(self, widget):
        # create a file chooser dialog to get a file name and format from the user
        fc = seqwriter.SeqWriterFileDialog(self, 'Export All Sequences')
        fc.setShowOptions(True)
        fc.set_current_folder(os.getcwd())

        response = fc.run()
        fname = fc.get_filename()
        fformat = fc.getFileFormat()
        include_fnames = fc.getIncludeFileNames()
        fc.destroy()
        if response != Gtk.ResponseType.OK:
            return

        # write out the sequences
        sw = seqwriter.SequenceWriterFactory.getSequenceWriter(fformat)
        try:
            sw.open(fname)
        except IOError:
            self.showMessage('The file "' + fname + '" could not be opened for writing.  ' +
                    'Verify that you have permission to write to the specified file and directory.')
            return

        for item in self.project:
            if item.getUseSequence():
                desc = item.getNotes()
                if item.isFile():
                    seqfname = item.getName()
                else:
                    children = item.getChildren()
                    seqfname = children[0].getName() + ', ' + children[1].getName()

                if not(include_fnames):
                    seqfname = ''

                sw.addUnalignedSequence(item.getCompactConsSequence(), seqfname, desc)

        try:
            sw.write()
        except seqwriter.SequenceWriterError as err:
            self.showMessage('Error: ' + str(err))

    def exportSelected(self, widget):
        # create a file chooser dialog to get a file name and format from the user
        fc = seqwriter.SeqWriterFileDialog(self, 'Export Selected Sequences')
        fc.setShowOptions(True)
        fc.set_current_folder(os.getcwd())

        response = fc.run()
        fname = fc.get_filename()
        fformat = fc.getFileFormat()
        include_fnames = fc.getIncludeFileNames()
        fc.destroy()
        if response != Gtk.ResponseType.OK:
            return

        # write out the sequences
        sw = seqwriter.SequenceWriterFactory.getSequenceWriter(fformat)
        try:
            sw.open(fname)
        except IOError:
            self.showMessage('The file "' + fname + '" could not be opened for writing.  ' +
                    'Verify that you have permission to write to the specified file and directory.')
            return

        items = self.projview.getSelection()

        for item in items:
            if item.hasParent():
                continue

            if item.getUseSequence():
                desc = item.getNotes()
                if item.isFile():
                    seqfname = item.getName()
                else:
                    children = item.getChildren()
                    seqfname = children[0].getName() + ', ' + children[1].getName()

                if not(include_fnames):
                    seqfname = ''

                sw.addUnalignedSequence(item.getCompactConsSequence(), seqfname, desc)

        try:
            sw.write()
        except seqwriter.SequenceWriterError as err:
            self.showMessage('Error: ' + str(err))

    def projectViewFiles(self, widget):
        items = self.projview.getSelection()

        # If there are a lot of items selected, make sure the user wants to
        # proceed.
        if len(items) > 4:
            response = self.showYesNoDialog(
                'This will open ' + str(len(items)) + ' trace file windows.  Do you want to continue?'
            )
            if response != Gtk.ResponseType.YES:
                return

        for item in items:
            idnum = item.getId()
            fullcons = item.getFullConsSequence()
            loaded_fullcons = False

            searchres = self.tw_manager.findByItemId(idnum)
            if searchres == None:
                seqtraces = self.getSeqTraces(item)
                if seqtraces == None:
                    continue

                csb = ModifiableConsensSeqBuilder(
                    seqtraces, self.project.getConsensSeqSettings()
                )

                # Try to load the saved consensus sequence, if it exists.
                if fullcons != '':
                    try:
                        csb.setConsensSequence(fullcons)
                        loaded_fullcons = True
                    except Exception:
                        self.showMessage(
                            'The saved consensus sequence cannot be used because its size is incorrect.  A new consensus sequence will be generated.'
                        )

                # Create a new trace window and add event handlers.
                newwin = self.tw_manager.newTraceWindow(csb, idnum)
                newwin.registerObserver('consensus_saved', self.traceWindowConsensusSaved)
                if loaded_fullcons:
                    # The saved consensus sequence was successfully loaded, so
                    # start with "Save" button disabled.
                    newwin.setSaveEnabled(False)

                newwin.setSeqFont(self.project.getFont())
                newwin.show()
                newwin.set_focus(None)
            else:
                # Show the existing trace window.
                searchres.present()

    def getSeqTraces(self, projectitem):
        seqtraces = list()

        # load the trace files
        if projectitem.isFile():
            seqt = self.openTraceFileFromItem(projectitem)
            if seqt == None:
                return None
            if projectitem.getIsReverse():
                seqt.reverseComplement()
            seqtraces.append(seqt)
        else:
            children = projectitem.getChildren()
            for child in children:
                seqt = self.openTraceFileFromItem(child)
                if seqt == None:
                    return None
                if child.getIsReverse():
                    seqt.reverseComplement()
                seqtraces.append(seqt)

        return seqtraces

    def openTraceFileFromItem(self, projectitem):
        fname = projectitem.getName()
        fullpath = os.path.join(self.project.getAbsTraceFileDir(), fname)

        return self.openTraceFileInternal(fullpath)

    def openTraceFileInternal(self, filepath):
        # get the appropriate SequenceTrace object
        try:
            seqt = sequencetrace.SequenceTraceFactory.loadTraceFile(filepath)
        except IOError:
            self.showMessage('The sequence trace file "' + filepath + '" could not be opened.  Verify that the file exists and that you have permission to read it.')
            return None
        except sequencetrace.TraceFileError as err:
            self.showMessage('Error opening "' + filepath + '".\n\n' + str(err))
            return None

        return seqt

    def traceWindowConsensusSaved(self, tracewindow, compact_consens, full_consens):
        itemid = self.tw_manager.getItemId(tracewindow)
        item = self.project.getItemById(itemid)

        item.setUseSequence(True)
        item.setConsensusSequence(compact_consens, full_consens)

        tracewindow.setSaveEnabled(False)

    def projectAddFiles(self, widget):
        # create a file chooser dialog to get a file name (or names) from the user
        fc = Gtk.FileChooserDialog(
            'Add Files to Project', self, Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_ADD, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        )
        fc.set_local_only(True)
        fc.set_select_multiple(True)
        fc.set_current_folder(self.project.getAbsTraceFileDir())
        f1 = Gtk.FileFilter()
        f1.set_name('trace files (*.ab1;*.scf;*.ztr)')
        f1.add_pattern('*.ztr')
        f1.add_pattern('*.ab1')
        f1.add_pattern('*.scf')
        f2 = Gtk.FileFilter()
        f2.set_name('all files (*)')
        f2.add_pattern('*')
        fc.add_filter(f1)
        fc.add_filter(f2)
        response = fc.run()
        filenames = fc.get_filenames()
        fc.destroy()
        if response != Gtk.ResponseType.OK:
            return

        for filepath in filenames:
            # check if the file already exists in the project
            if self.project.isFileInProject(filepath):
                response = self.showYesNoDialog('The file "' + filepath
                        + '" has already been added to this project.  Do you want to add it anyway?')
                if response != Gtk.ResponseType.YES:
                    continue

            self.project.addFiles((filepath,))

    def projectRemoveFiles(self, widget):
        # confirm this is what the user actually wants to do
        response = self.showYesNoDialog('Are you sure you want to remove the selected file(s) from the project?  This operation cannot be undone.')
        if response != Gtk.ResponseType.YES:
            return False

        items = self.projview.getSelection()
        for item in items:
            # if there is an open trace window for the file or an associative node that contains
            # it, close the window(s) first
            self.tw_manager.closeByItemId(item.getId())
            if item.hasParent():
                parent = item.getParent()
                self.tw_manager.closeByItemId(parent.getId())

        # now remove the files from the project
        self.project.removeFileItems(items)

    def deleteAllSeqs(self, widget):
        # confirm this is what the user actually wants to do
        response = self.showYesNoDialog('Are you sure you want to delete all saved consensus sequences?  This operation cannot be undone.')
        if response != Gtk.ResponseType.YES:
            return

        for item in self.project:
            item.deleteConsensusSequence()
            for child in item.getChildren():
                child.deleteConsensusSequence()

    def deleteSelSeqs(self, widget):
        # confirm this is what the user actually wants to do
        response = self.showYesNoDialog('Are you sure you want to delete the selected consensus sequences?  This operation cannot be undone.')
        if response != Gtk.ResponseType.YES:
            return

        items = self.projview.getSelection()

        for item in items:
            item.deleteConsensusSequence()

    def generateAllSequences(self, widget):
        # confirm this is what the user actually wants to do
        response = self.showYesNoDialog('Are you sure you want to generate finished sequences for all trace files?  This will overwrite any sequences that have already been saved.')
        if response != Gtk.ResponseType.YES:
            return

        self.generateSequencesInternal(iter(self.project), 'Generating sequences for all trace files...')

    def generateSelectedSequences(self, widget):
        # confirm this is what the user actually wants to do
        response = self.showYesNoDialog('Are you sure you want to generate finished sequences for the selected trace files?  This will overwrite any sequences that have already been saved.')
        if response != Gtk.ResponseType.YES:
            return

        items = self.projview.getSelection()
        self.generateSequencesInternal(items, 'Generating sequences for selected trace files...')

    def generateSequencesInternal(self, itemlist, progressmsg):
        # create a progress bar dialog
        diag = ProgressBarDialog(self, progressmsg)
        diag.show()

        cnt = 0.0
        for item in itemlist:
            # update the progress bar and check if the user canceled the operation
            diag.updateProgress(cnt / len(itemlist))
            cnt += 1
            if diag.getIsCanceled():
                break

            if item.isFile() and item.hasParent():
                continue

            # load the trace files
            seqtraces = self.getSeqTraces(item)
            if seqtraces == None:
                continue

            # get and save the consensus sequence
            csb = ConsensSeqBuilder(seqtraces, self.project.getConsensSeqSettings())
            full_cons = csb.getConsensus()
            compact_cons = csb.getCompactConsensus()
            item.setUseSequence(True)
            item.setConsensusSequence(compact_cons, full_cons)

        diag.destroy()

    def projectAssociateFiles(self, widget):
        diag = EntryDialog(self, 'Group Name', 'Name for new forward/reverse group:', 'new_group', 40)
        response = diag.run()
        name = diag.get_text()
        while (name == '') and (response == Gtk.ResponseType.OK):
            response = diag.run()
            name = diag.get_text()

        diag.destroy()

        if response != Gtk.ResponseType.OK:
            return

        items = self.projview.getSelection()
        self.project.associateItems(items, name)

    def projectDissociateFiles(self, widget):
        # confirm this is what the user actually wants to do
        response = self.showYesNoDialog('Are you sure you want to remove the selected forward/reverse groupings?')
        if response != Gtk.ResponseType.YES:
            return

        items = self.projview.getSelection()

        # Only get the items that are not files.
        groupitems = []
        for item in items:
            if not(item.isFile()):
                groupitems.append(item)

        for item in groupitems:
            # If there are any open trace windows for this group, close
            # them first.
            self.tw_manager.closeByItemId(item.getId())
            self.project.removeAssociativeItem(item)

    def findFwdRev(self, widget):
        # confirm this is what the user wants to do
        response = self.showYesNoDialog('Attempt to identify selected files as forward or reverse reads?')
        if response != Gtk.ResponseType.YES:
            return

        items = self.projview.getSelection()
        for item in items:
            if item.isFile():
                if os.path.basename(item.getName()).find(self.project.getFwdTraceSearchStr()) != -1:
                    item.setIsReverse(False)
                elif os.path.basename(item.getName()).find(self.project.getRevTraceSearchStr()) != -1:
                    item.setIsReverse(True)

    def projectAssociateAllFiles(self, widget):
        match_iter = self.project.getFwdRevMatchIter()
        self.processFwdRevMatches(match_iter)

    def projectAssociateSelectedFiles(self, widget):
        items = self.projview.getSelection()

        match_iter = self.project.getFwdRevMatchIter(items)
        self.processFwdRevMatches(match_iter)

    def processFwdRevMatches(self, match_iter):
        pair_cnt = 0
        show_confirm = True
        do_associate = False

        for pair in match_iter:
            pair_cnt += 1
            fname1 = pair[0].getFileNames()[0]
            fname2 = pair[1].getFileNames()[0]

            # confirm the user wants to group these two files
            if show_confirm:
                msgtxt = 'The following files appear to match:\n\n' + fname1 + '\n' + fname2
                msgtxt += '\n\nDo you want to group these files as matching forward and reverse sequencing traces?'
                response = self.showYesToAllDialog(msgtxt)

                if (response == Gtk.ResponseType.YES) or (response == dialgs.YES_TO_ALL):
                    if response == dialgs.YES_TO_ALL:
                        show_confirm = False
                    do_associate = True
                elif response == Gtk.ResponseType.NO:
                    do_associate = False
                else:
                    break

            if do_associate:
                # make sure the forward/reverse properties are set correctly
                pair[0].setIsReverse(False)
                pair[1].setIsReverse(True)
                self.project.associateItems(pair[0:2], pair[2])

        if pair_cnt == 0:
            self.showMessage('No matching forward and reverse sequencing trace files were found.', Gtk.MessageType.INFO)

    def showAbout(self, widget):
        diag = Gtk.AboutDialog(parent=self)
        diag.set_program_name('SeqTrace')
        diag.set_version('1.0.0')
        diag.set_copyright('Copyright \xC2\xA9 2018 Brian J. Stucky')
        #diag.set_authors(['Brian Stucky'])
        diag.set_comments('by Brian Stucky\n\nA program for viewing and processing Sanger sequencing trace files.')
        diag.set_license(
        '''Copyright (C) 2018 Brian J. Stucky

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.''')
        diag.set_logo(GdkPixbuf.Pixbuf.new_from_file(images_folder + '/about.png'))
        diag.run()
        diag.destroy()

    def deleteEvent(self, widget, data=None):
        if self.project_open:
            if not(self.closeProject(None)):
                return True

        # close any remaining trace windows that are still open
        self.tw_manager.closeAllTraceWindows()

        Gtk.main_quit()

