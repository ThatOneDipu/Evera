pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'hidamari')  # Python package name stays hidamari
gnome = import('gnome')

gnome.compile_resources('evera',
  'evera.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'evera.in',
  output: 'evera',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

hidamari_sources = [
  '__init__.py',
  '__main__.py',
  'commons.py',
  'market.py',
  'menu.py',
  'server.py',
  'monitor.py',
  'utils.py',
  'yt_utils.py'
]

exclude_dir = [
  '__pycache__'
]

install_subdir('gui', install_dir: moduledir, exclude_directories: exclude_dir)
install_subdir('player', install_dir: moduledir, exclude_directories: exclude_dir)
install_data(hidamari_sources, install_dir: moduledir)
