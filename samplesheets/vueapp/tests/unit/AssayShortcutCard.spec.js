import { createLocalVue, mount } from '@vue/test-utils'
import BootstrapVue from 'bootstrap-vue'
import VueClipboard from 'vue-clipboard2'
import AssayShortcutCard from '@/components/AssayShortcutCard.vue'
import sodarContext from './data/sodarContext.json'
import assayShortcuts from './data/assayShortcuts.json'

// Set up extended Vue constructor
const localVue = createLocalVue()
localVue.use(BootstrapVue)
localVue.use(VueClipboard)

// Init data
let propsData

describe('AssayShortcutCard.vue', () => {
  function getPropsData () {
    return {
      sodarContext: JSON.parse(JSON.stringify(sodarContext)),
      assayShortcuts: JSON.parse(JSON.stringify(assayShortcuts)),
      modalComponent: null,
      notifyCallback: null
    }
  }

  beforeAll(() => {
    // Disable warnings
    jest.spyOn(console, 'warn').mockImplementation(jest.fn())
  })

  beforeEach(() => {
    propsData = getPropsData()
    jest.resetModules()
    jest.clearAllMocks()
  })

  it('renders assay shortcuts', () => {
    const wrapper = mount(AssayShortcutCard, { localVue, propsData: propsData })

    expect(wrapper.findAll('.sodar-ss-vue-assay-shortcut').length).toBe(2)
    expect(wrapper.findAll('.fa-puzzle-piece').length).toBe(0)
    for (let i = 0; i < 2; i++) {
      expect(wrapper.findAll('.sodar-vue-popup-list-btn').at(i).exists()).toBe(true)
      expect(wrapper.findAll('.sodar-irods-copy-path-btn').at(i)).not.toContain('disabled')
      expect(wrapper.findAll('.sodar-irods-copy-dav-btn').at(i)).not.toContain('disabled')
      expect(wrapper.findAll('.sodar-irods-dav-btn').at(i)).not.toContain('disabled')
    }
  })

  it('renders extra assay plugin shortcut', () => {
    propsData.assayShortcuts.push({
      id: 'plugin_shortcut',
      label: 'Plugin Shortcut',
      path: '/omicsZone/projects/00/00000000-0000-0000-0000-000000000000/sample_data/study_11111111-1111-1111-1111-111111111111/assay_22222222-2222-2222-2222-222222222222/PluginShortcut'
    })
    const wrapper = mount(AssayShortcutCard, { localVue, propsData: propsData })

    expect(wrapper.findAll('.sodar-ss-vue-assay-shortcut').length).toBe(3)
    expect(wrapper.findAll('.fa-puzzle-piece').length).toBe(1)
  })

  it('renders disabled shortcuts', () => {
    propsData.assayShortcuts[0].enabled = false
    propsData.assayShortcuts[1].enabled = false
    const wrapper = mount(AssayShortcutCard, { localVue, propsData: propsData })

    expect(wrapper.findAll('.sodar-ss-vue-assay-shortcut').length).toBe(2)
    for (let i = 0; i < 2; i++) {
      expect(wrapper.findAll('.sodar-vue-popup-list-btn').at(i).exists()).toBe(true)
      expect(wrapper.findAll('.sodar-vue-popup-list-btn').at(i).attributes().disabled).toBe('disabled')
      expect(wrapper.findAll('.sodar-irods-copy-path-btn').at(i).attributes().disabled).toBe('disabled')
      expect(wrapper.findAll('.sodar-irods-copy-dav-btn').at(i).attributes().disabled).toBe('disabled')
      expect(wrapper.findAll('.sodar-irods-dav-btn').at(i).classes()).toContain('disabled')
    }
  })

  it('calls copy event and notifyCallback on iRODS path copy button click', () => {
    propsData.notifyCallback = jest.fn()
    const wrapper = mount(AssayShortcutCard, { localVue, propsData: propsData })
    const spyNotifyCallback = jest.spyOn(wrapper.vm, 'notifyCallback')
    wrapper.setMethods({ notifyCallback: spyNotifyCallback })

    expect(spyNotifyCallback).not.toHaveBeenCalled()
    wrapper.find('.sodar-irods-copy-path-btn').trigger('click')
    expect(spyNotifyCallback).toHaveBeenCalled()
  })

  it('opens modal component on iRODS dir list button click', () => {
    propsData.showFileList = true
    propsData.modalComponent = {
      setTitle: jest.fn(),
      showModal: jest.fn()
    }
    const wrapper = mount(AssayShortcutCard, { localVue, propsData: propsData })
    const spySetTitle = jest.spyOn(wrapper.props().modalComponent, 'setTitle')
    const spyShowModal = jest.spyOn(wrapper.props().modalComponent, 'showModal')

    expect(spySetTitle).not.toHaveBeenCalled()
    expect(spyShowModal).not.toHaveBeenCalled()
    wrapper.find('.sodar-vue-popup-list-btn').trigger('click')
    expect(spySetTitle).toHaveBeenCalled()
    expect(spyShowModal).toHaveBeenCalled()
  })
})