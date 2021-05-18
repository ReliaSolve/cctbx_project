import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir) 


from io import StringIO
# The test data:
#
# The first portion is to test membership in every cluster.
# The second portion is to test triage by out of bounds angle
# for each dihedral angle.
# The third portion is a manually selected group of test cases from real files
# designed to test each code path through membership(). The first residue from 
# each pair has intentionally been damaged so that it will not produce separate
# output from a report.
data=''' :1a: : : : Z:  9999.000: 9999.000: 9999.000:   81.495:  212.250:  288.831:  180.000
 :1a: : : : Z:   294.967:  173.990:   53.550:   81.035: 9999.000: 9999.000:  180.000
 :1m: : : : Z:  9999.000: 9999.000: 9999.000:   83.513:  218.120:  291.593:  180.000
 :1m: : : : Z:   292.247:  222.300:   58.067:   86.093: 9999.000: 9999.000:  180.000
 :1L: : : : Z:  9999.000: 9999.000: 9999.000:   85.664:  245.014:  268.257:  180.000
 :1L: : : : Z:   303.879:  138.164:   61.950:   79.457: 9999.000: 9999.000:  180.000
 :&a: : : : Z:  9999.000: 9999.000: 9999.000:   82.112:  190.682:  264.945:  180.000
 :&a: : : : Z:   295.967:  181.839:   51.455:   81.512: 9999.000: 9999.000:  180.000
 :7a: : : : Z:  9999.000: 9999.000: 9999.000:   83.414:  217.400:  222.006:  180.000
 :7a: : : : Z:   302.856:  160.719:   49.097:   82.444: 9999.000: 9999.000:  180.000
 :3a: : : : Z:  9999.000: 9999.000: 9999.000:   85.072:  216.324:  173.276:  180.000
 :3a: : : : Z:   289.320:  164.132:   45.876:   84.956: 9999.000: 9999.000:  180.000
 :9a: : : : Z:  9999.000: 9999.000: 9999.000:   83.179:  210.347:  121.474:  180.000
 :9a: : : : Z:   288.568:  157.268:   49.347:   81.047: 9999.000: 9999.000:  180.000
 :1g: : : : Z:  9999.000: 9999.000: 9999.000:   80.888:  218.636:  290.735:  180.000
 :1g: : : : Z:   167.447:  159.565:   51.326:   85.213: 9999.000: 9999.000:  180.000
 :7d: : : : Z:  9999.000: 9999.000: 9999.000:   83.856:  238.750:  256.875:  180.000
 :7d: : : : Z:    69.562:  170.200:   52.800:   85.287: 9999.000: 9999.000:  180.000
 :3d: : : : Z:  9999.000: 9999.000: 9999.000:   85.295:  244.085:  203.815:  180.000
 :3d: : : : Z:    65.880:  181.130:   54.680:   86.035: 9999.000: 9999.000:  180.000
 :5d: : : : Z:  9999.000: 9999.000: 9999.000:   79.671:  202.471:   63.064:  180.000
 :5d: : : : Z:    68.164:  143.450:   49.664:   82.757: 9999.000: 9999.000:  180.000
 :3g: : : : Z:  9999.000: 9999.000: 9999.000:   84.000:  195.000:  146.000:  180.000
 :3g: : : : Z:   170.000:  170.000:   52.000:   84.000: 9999.000: 9999.000:  180.000
 :1e: : : : Z:  9999.000: 9999.000: 9999.000:   80.514:  200.545:  280.510:  180.000
 :1e: : : : Z:   249.314:   82.662:  167.890:   85.507: 9999.000: 9999.000:  180.000
 :1c: : : : Z:  9999.000: 9999.000: 9999.000:   80.223:  196.591:  291.299:  180.000
 :1c: : : : Z:   153.060:  194.379:  179.061:   83.648: 9999.000: 9999.000:  180.000
 :1f: : : : Z:  9999.000: 9999.000: 9999.000:   81.395:  203.030:  294.445:  180.000
 :1f: : : : Z:   172.195:  138.540:  175.565:   84.470: 9999.000: 9999.000:  180.000
 :5j: : : : Z:  9999.000: 9999.000: 9999.000:   87.417:  223.558:   80.175:  180.000
 :5j: : : : Z:    66.667:  109.150:  176.475:   83.833: 9999.000: 9999.000:  180.000
 :5n: : : : Z:  9999.000: 9999.000: 9999.000:   86.055:  246.502:  100.392:  180.000
 :5n: : : : Z:    73.595:  213.752:  183.395:   85.483: 9999.000: 9999.000:  180.000
 :!!: : : : Z:  9999.000: 9999.000: 9999.000:    0.000:    0.000:    0.000:    0.000
 :!!: : : : Z:     0.000:    0.000:    0.000:    0.000: 9999.000: 9999.000:    0.000
 :1b: : : : Z:  9999.000: 9999.000: 9999.000:   84.215:  215.014:  288.672:  180.000
 :1b: : : : Z:   300.420:  177.476:   58.307:  144.841: 9999.000: 9999.000:  180.000
 :1[: : : : Z:  9999.000: 9999.000: 9999.000:   82.731:  220.463:  288.665:  180.000
 :1[: : : : Z:   296.983:  221.654:   54.213:  143.771: 9999.000: 9999.000:  180.000
 :3b: : : : Z:  9999.000: 9999.000: 9999.000:   84.700:  226.400:  168.336:  180.000
 :3b: : : : Z:   292.771:  177.629:   48.629:  147.950: 9999.000: 9999.000:  180.000
 :1z: : : : Z:  9999.000: 9999.000: 9999.000:   83.358:  206.042:  277.567:  180.000
 :1z: : : : Z:   195.700:  161.600:   50.750:  145.258: 9999.000: 9999.000:  180.000
 :5z: : : : Z:  9999.000: 9999.000: 9999.000:   82.614:  206.440:   52.524:  180.000
 :5z: : : : Z:   163.669:  148.421:   50.176:  147.590: 9999.000: 9999.000:  180.000
 :7p: : : : Z:  9999.000: 9999.000: 9999.000:   84.285:  236.600:  220.400:  180.000
 :7p: : : : Z:    68.300:  200.122:   53.693:  145.730: 9999.000: 9999.000:  180.000
 :5p: : : : Z:  9999.000: 9999.000: 9999.000:   84.457:  213.286:   69.086:  180.000
 :5p: : : : Z:    75.500:  156.671:   57.486:  147.686: 9999.000: 9999.000:  180.000
 :1t: : : : Z:  9999.000: 9999.000: 9999.000:   81.200:  199.243:  288.986:  180.000
 :1t: : : : Z:   180.286:  194.743:  178.200:  147.386: 9999.000: 9999.000:  180.000
 :5q: : : : Z:  9999.000: 9999.000: 9999.000:   82.133:  204.933:   69.483:  180.000
 :5q: : : : Z:    63.417:  115.233:  176.283:  145.733: 9999.000: 9999.000:  180.000
 :1o: : : : Z:  9999.000: 9999.000: 9999.000:   83.977:  216.508:  287.192:  180.000
 :1o: : : : Z:   297.254:  225.154:  293.738:  150.677: 9999.000: 9999.000:  180.000
 :7r: : : : Z:  9999.000: 9999.000: 9999.000:   84.606:  232.856:  248.125:  180.000
 :7r: : : : Z:    63.269:  181.975:  295.744:  149.744: 9999.000: 9999.000:  180.000
 :5r: : : : Z:  9999.000: 9999.000: 9999.000:   83.000:  196.900:   65.350:  180.000
 :5r: : : : Z:    60.150:  138.425:  292.550:  154.275: 9999.000: 9999.000:  180.000
 :2a: : : : Z:  9999.000: 9999.000: 9999.000:  145.399:  260.339:  288.756:  180.000
 :2a: : : : Z:   288.444:  192.733:   53.097:   84.067: 9999.000: 9999.000:  180.000
 :4a: : : : Z:  9999.000: 9999.000: 9999.000:  146.275:  259.783:  169.958:  180.000
 :4a: : : : Z:   298.450:  169.583:   50.908:   83.967: 9999.000: 9999.000:  180.000
 :0a: : : : Z:  9999.000: 9999.000: 9999.000:  149.286:  223.159:  139.421:  180.000
 :0a: : : : Z:   284.559:  158.107:   47.900:   84.424: 9999.000: 9999.000:  180.000
 :#a: : : : Z:  9999.000: 9999.000: 9999.000:  148.006:  191.944:  146.231:  180.000
 :#a: : : : Z:   289.288:  150.781:   42.419:   84.956: 9999.000: 9999.000:  180.000
 :4g: : : : Z:  9999.000: 9999.000: 9999.000:  148.028:  256.922:  165.194:  180.000
 :4g: : : : Z:   204.961:  165.194:   49.383:   82.983: 9999.000: 9999.000:  180.000
 :6g: : : : Z:  9999.000: 9999.000: 9999.000:  145.337:  262.869:   79.588:  180.000
 :6g: : : : Z:   203.863:  189.688:   58.000:   84.900: 9999.000: 9999.000:  180.000
 :8d: : : : Z:  9999.000: 9999.000: 9999.000:  148.992:  270.596:  240.892:  180.000
 :8d: : : : Z:    62.225:  176.271:   53.600:   87.262: 9999.000: 9999.000:  180.000
 :4d: : : : Z:  9999.000: 9999.000: 9999.000:  149.822:  249.956:  187.678:  180.000
 :4d: : : : Z:    80.433:  198.133:   61.000:   89.378: 9999.000: 9999.000:  180.000
 :6d: : : : Z:  9999.000: 9999.000: 9999.000:  146.922:  241.222:   88.894:  180.000
 :6d: : : : Z:    59.344:  160.683:   52.333:   83.417: 9999.000: 9999.000:  180.000
 :2g: : : : Z:  9999.000: 9999.000: 9999.000:  141.900:  258.383:  286.517:  180.000
 :2g: : : : Z:   178.267:  165.217:   48.350:   84.783: 9999.000: 9999.000:  180.000
 :2h: : : : Z:  9999.000: 9999.000: 9999.000:  147.782:  260.712:  290.424:  180.000
 :2h: : : : Z:   296.200:  177.282:  175.594:   86.565: 9999.000: 9999.000:  180.000
 :4n: : : : Z:  9999.000: 9999.000: 9999.000:  143.722:  227.256:  203.789:  180.000
 :4n: : : : Z:    73.856:  216.733:  194.444:   80.911: 9999.000: 9999.000:  180.000
 :0i: : : : Z:  9999.000: 9999.000: 9999.000:  148.717:  274.683:  100.283:  180.000
 :0i: : : : Z:    80.600:  248.133:  181.817:   82.600: 9999.000: 9999.000:  180.000
 :6n: : : : Z:  9999.000: 9999.000: 9999.000:  150.311:  268.383:   84.972:  180.000
 :6n: : : : Z:    63.811:  191.483:  176.644:   85.600: 9999.000: 9999.000:  180.000
 :6j: : : : Z:  9999.000: 9999.000: 9999.000:  141.633:  244.100:   66.056:  180.000
 :6j: : : : Z:    71.667:  122.167:  182.200:   83.622: 9999.000: 9999.000:  180.000
 :0k: : : : Z:  9999.000: 9999.000: 9999.000:  149.070:  249.780:  111.520:  180.000
 :0k: : : : Z:   278.370:  207.780:  287.820:   86.650: 9999.000: 9999.000:  180.000
 :2[: : : : Z:  9999.000: 9999.000: 9999.000:  146.383:  259.402:  291.275:  180.000
 :2[: : : : Z:   291.982:  210.048:   54.412:  147.760: 9999.000: 9999.000:  180.000
 :4b: : : : Z:  9999.000: 9999.000: 9999.000:  145.256:  244.622:  162.822:  180.000
 :4b: : : : Z:   294.159:  171.630:   45.900:  145.804: 9999.000: 9999.000:  180.000
 :0b: : : : Z:  9999.000: 9999.000: 9999.000:  147.593:  248.421:  112.086:  180.000
 :0b: : : : Z:   274.943:  164.764:   56.843:  146.264: 9999.000: 9999.000:  180.000
 :4p: : : : Z:  9999.000: 9999.000: 9999.000:  150.077:  260.246:  213.785:  180.000
 :4p: : : : Z:    71.900:  207.638:   56.715:  148.131: 9999.000: 9999.000:  180.000
 :6p: : : : Z:  9999.000: 9999.000: 9999.000:  146.415:  257.831:   89.597:  180.000
 :6p: : : : Z:    67.923:  173.051:   55.513:  147.623: 9999.000: 9999.000:  180.000
 :2z: : : : Z:  9999.000: 9999.000: 9999.000:  142.900:  236.550:  268.800:  180.000
 :2z: : : : Z:   180.783:  185.133:   54.467:  143.350: 9999.000: 9999.000:  180.000
 :4s: : : : Z:  9999.000: 9999.000: 9999.000:  149.863:  247.562:  170.488:  180.000
 :4s: : : : Z:   277.938:   84.425:  176.413:  148.087: 9999.000: 9999.000:  180.000
 :2u: : : : Z:  9999.000: 9999.000: 9999.000:  143.940:  258.200:  298.240:  180.000
 :2u: : : : Z:   279.640:  183.680:  183.080:  145.120: 9999.000: 9999.000:  180.000
 :2o: : : : Z:  9999.000: 9999.000: 9999.000:  147.342:  256.475:  295.508:  180.000
 :2o: : : : Z:   287.408:  194.525:  293.725:  150.458: 9999.000: 9999.000:  180.000
 :epsilon: : : : Z:   294.967:  173.990:   53.550:   81.495:  154.000:  288.831:  180.000
 :epsilon: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000
 :alpha: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000  
 :alpha: : : : Z:    24.000:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000  
 :beta: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000   
 :beta: : : : Z:   294.967:   49.000:   53.550:   81.495:  212.250:  288.831:  180.000   
 :zeta: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:   24.000:  180.000   
 :zeta: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000   
 :delta-1: : : : Z:   294.967:  173.990:   53.550:   59.000:  212.250:  288.831:  180.000
 :delta-1: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000
 :gamma: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000
 :gamma: : : : Z:   294.967:  173.990:  139.000:   81.495:  212.250:  288.831:  180.000
 :delta: : : : Z:   294.967:  173.990:   53.550:   81.495:  212.250:  288.831:  180.000
 :delta: : : : Z:   294.967:  173.990:   53.550:   59.000:  212.250:  288.831:  180.000
2xLk:1: C:  11: : :  G:__?__:__?__:__?__:81.132:-127.583:-70.677
2xLk:1: C:  12: : :  U:169.008:153.891:51.391:80.277:-135.347:-70.614
3cgp:1: B:  19: : :  U:__?__:__?__:__?__:82.839:-147.528:-179.087
3cgp:1: B:  20: : :  A:139.983:-154.445:63.134:88.055:-145.599:70.874
4pco:1: B:   3: : :  U:__?__:__?__:__?__:77.659:-165.227:-68.525
4pco:1: B:   4: : :  G:151.914:-179.903:176.058:83.039:-148.171:-66.728
5b2q:1: B:  62: : :  G:__?__:__?__:__?__:83.537:-131.816:-116.417
5b2q:1: B:  63: : :  U:-69.320:-146.615:47.107:147.038:-148.815:45.665
6gc5:1: F:   2: : :  U:__?__:__?__:__?__:144.610:-116.227:152.694
6gc5:1: F:   3: : :  U:-66.167:162.580:41.697:145.644:-122.673:127.881
3bns:1: A:  21: : :  C:__?__:__?__:__?__:76.224:-166.174:-73.594
3bns:1: A:  22: : :  G:150.784:-158.788:175.706:87.605:-146.172:-63.516
3gm7:1: H:   5: : :  U:__?__:__?__:__?__:68.910:-153.989:-56.381
3gm7:1: H:   6: : :  G:-105.747:164.057:92.120:74.597:-150.523:-79.724
6qit:1: A:   2: : :  C:__?__:__?__:__?__:82.169:-138.695:-63.417
6qit:1: A:   3: : :  A:-71.504:-131.618:54.061:144.409:-95.827:-140.754
3rer:1: K:   7: : :  U:__?__:__?__:__?__:87.510:-99.276:-118.108
3rer:1: K:   8: : :  A:-66.924:-158.118:48.287:81.250:__?__:__?__
3diL:1: A:  59: : :  C:__?__:__?__:__?__:80.668:-145.667:-36.026
3diL:1: A:  60: : :  G:-143.441:115.188:149.951:86.379:-141.567:-69.901
5ho4:1: B:   3: : :  G:__?__:__?__:__?__:160.213:-123.685:-174.677
5ho4:1: B:   4: : :  G:-107.676:163.883:39.081:85.911:-157.392:-71.638
4mcf:1: E:   4: : :  U:__?__:__?__:__?__:78.239:-156.881:-70.399
4mcf:1: E:   5: : :  G:-91.794:163.594:87.552:70.675:-141.886:-72.556
3pdr:1: A:  59: : :  C:__?__:__?__:__?__:80.441:-149.674:-76.690
3pdr:1: A:  60: : :  A:-62.415:171.383:47.537:79.461:-145.680:-71.359
3gm7:1: G:   1: : :  C:__?__:__?__:__?__:84.065:-128.784:-61.905
3gm7:1: G:   2: : :  U:-76.914:-166.398:55.279:74.218:-157.766:-64.720
6h0r:1: B:  15: : :  U:__?__:__?__:__?__:83.971:-122.349:-103.636
6h0r:1: B:  16: : :  U:-30.804:145.657:33.314:81.109:-141.719:-75.527
2zko:1: C:  13: : :  G:__?__:__?__:__?__:76.629:-150.027:-67.298
2zko:1: C:  14: : :  C:-70.016:164.567:71.735:76.499:-160.106:-73.474
3pdr:1: X: 138: : :  U:__?__:__?__:__?__:77.324:-177.192:-105.412
3pdr:1: X: 139: : :  A:-46.950:179.570:49.599:71.442:-143.233:-61.461
4jah:1: B:  10: : :  U:__?__:__?__:__?__:85.890:-164.804:-95.055
4jah:1: B:  11: : :  G:-64.134:178.767:49.773:77.067:-152.496:-70.128
3diL:1: A:  13: : :  C:__?__:__?__:__?__:135.303:-125.074:-69.725
3diL:1: A:  14: : :  G:75.452:147.741:32.719:83.048:-146.012:-75.223
3pdr:1: X: 132: : :  U:__?__:__?__:__?__:77.469:-157.795:-115.458
3pdr:1: X: 133: : :  U:47.309:136.943:-25.259:83.460:-150.210:-61.763
'''

canonicalOutput='''
:1a: : : : Z 33 p 1a 1.000
 :1m: : : : Z 33 p 1m 1.000
 :1L: : : : Z 33 p 1L 1.000
 :&a: : : : Z 33 p &a 1.000
 :7a: : : : Z 33 p 7a 1.000
 :3a: : : : Z 33 p 3a 1.000
 :9a: : : : Z 33 p 9a 1.000
 :1g: : : : Z 33 p 1g 1.000
 :7d: : : : Z 33 p 7d 1.000
 :3d: : : : Z 33 p 3d 1.000
 :5d: : : : Z 33 p 5d 1.000
 :3g: : : : Z 33 p 3g 1.000 wannabe
 :1e: : : : Z 33 t 1e 1.000
 :1c: : : : Z 33 t 1c 1.000
 :1f: : : : Z 33 t 1f 1.000
 :5j: : : : Z 33 t 5j 1.000
 :5n: : : : Z 33 t 5n 1.000 wannabe
 :!!: : : : Z trig !! 0.000 epsilon-1
 :1b: : : : Z 32 p 1b 1.000
 :1[: : : : Z 32 p 1[ 1.000
 :3b: : : : Z 32 p 3b 1.000
 :1z: : : : Z 32 p 1z 1.000
 :5z: : : : Z 32 p 5z 1.000
 :7p: : : : Z 32 p 7p 1.000
 :5p: : : : Z 32 p 5p 1.000 wannabe
 :1t: : : : Z 32 t 1t 1.000
 :5q: : : : Z 32 t 5q 1.000
 :1o: : : : Z 32 m 1o 1.000
 :7r: : : : Z 32 m 7r 1.000
 :5r: : : : Z 32 m 5r 1.000 wannabe
 :2a: : : : Z 23 p 2a 1.000
 :4a: : : : Z 23 p 4a 1.000
 :0a: : : : Z 23 p 0a 1.000
 :#a: : : : Z 23 p #a 1.000
 :4g: : : : Z 23 p 4g 1.000
 :6g: : : : Z 23 p 6g 1.000
 :8d: : : : Z 23 p 8d 1.000
 :4d: : : : Z 23 p 4d 1.000
 :6d: : : : Z 23 p 6d 1.000
 :2g: : : : Z 23 p 2g 1.000 wannabe
 :2h: : : : Z 23 t 2h 1.000
 :4n: : : : Z 23 t 4n 1.000
 :0i: : : : Z 23 t 0i 1.000
 :6n: : : : Z 23 t 6n 1.000
 :6j: : : : Z 23 t 6j 1.000
 :0k: : : : Z 23 m 0k 1.000 wannabe
 :2[: : : : Z 22 p 2[ 1.000
 :4b: : : : Z 22 p 4b 1.000
 :0b: : : : Z 22 p 0b 1.000
 :4p: : : : Z 22 p 4p 1.000
 :6p: : : : Z 22 p 6p 1.000
 :2z: : : : Z 22 p 2z 1.000 wannabe
 :4s: : : : Z 22 t 4s 1.000
 :2u: : : : Z 22 t 2u 1.000 wannabe
 :2o: : : : Z 22 m 2o 1.000
 :epsilon: : : : Z trig !! 0.000 epsilon-1
 :alpha: : : : Z 33 p 1a 0.999
 :alpha: : : : Z trig !! 0.000 alpha
 :beta: : : : Z 33 p 1a 0.999
 :beta: : : : Z trig !! 0.000 beta
 :zeta: : : : Z 33 p 1a 0.999
 :zeta: : : : Z trig !! 0.000 zeta-1
 :delta-1: : : : Z trig !! 0.000 delta
 :delta-1: : : : Z trig !! 0.000 delta-1
 :gamma: : : : Z 33 p 1a 0.999
 :gamma: : : : Z trig !! 0.000 gamma
 :delta: : : : Z 33 p 1a 0.999
 :delta: : : : Z trig !! 0.000 delta
 :epsilon: : : : Z:   294.967 trig !! 0.000 delta
 :alpha: : : : Z:   294.967 trig !! 0.000 delta-1
 :alpha: : : : Z:    24.000 trig !! 0.000 delta-1
 :beta: : : : Z:   294.967 trig !! 0.000 delta-1
 :beta: : : : Z:   294.967 trig !! 0.000 delta-1
 :zeta: : : : Z:   294.967 trig !! 0.000 delta-1
 :zeta: : : : Z:   294.967 trig !! 0.000 epsilon-1
 :delta-1: : : : Z:   294.967 trig !! 0.000 delta-1
 :delta-1: : : : Z:   294.967 trig !! 0.000 delta-1
 :gamma: : : : Z:   294.967 trig !! 0.000 delta-1
 :gamma: : : : Z:   294.967 trig !! 0.000 delta-1
 :delta: : : : Z:   294.967 trig !! 0.000 delta-1
 :delta: : : : Z:   294.967 trig !! 0.000 delta-1
2xLk:1: C:  12: : :  U 33 p 1g 0.839 1-only-one
3cgp:1: B:  20: : :  A 33 p 3g 0.040 1-only-one wannabe
4pco:1: B:   4: : :  G 33 t 1c 0.890 2-BETWEEN-dom-sat(   0.22|  0.913)
5b2q:1: B:  63: : :  U 32 p 1[ 0.072 2-BETWEEN-dom-sat(  0.941|  0.829)
6gc5:1: F:   3: : :  U 22 p 4b 0.889 2-None-dom
3bns:1: A:  22: : :  G 33 t 1c 0.901 2-OUTSIDE-dom
3gm7:1: H:   6: : :  G 33 p !! 0.000 7D dist 1a
6qit:1: A:   3: : :  A 32 p 1[ 0.899 2-OUTSIDE-sat
3rer:1: K:   8: : :  A 33 p 7a 0.047 2-not-sat
3diL:1: A:  60: : :  G 33 t !! 0.000 7D dist 1e
5ho4:1: B:   4: : :  G 23 p !! 0.000 7D dist 4a
4mcf:1: E:   5: : :  G 33 p !! 0.000 7D dist 1a
3pdr:1: A:  60: : :  A 33 p 1a 0.916 4-BETWEEN-dom-sat(    0.1|    1.2)
3gm7:1: G:   2: : :  U 33 p 1a 0.589 4-BETWEEN-dom-sat(  0.428|  0.904)
6h0r:1: B:  16: : :  U 33 p 1L 0.033 4-BETWEEN-dom-sat(  0.862|  0.655)
2zko:1: C:  14: : :  C 33 p 1a 0.444 4-OUTSIDE-dom
3pdr:1: X: 139: : :  A 33 p &a 0.555 4-OUTSIDE-sat
4jah:1: B:  11: : :  G 33 p &a 0.912 5-BETWEEN-dom-sat(  0.442|  0.226)
3diL:1: A:  14: : :  G 23 p !! 0.000 outlier distance 1.01
3pdr:1: X: 133: : :  U 33 m !! 0.000 vacant bin
'''
 
 # here before importing suitename, is an opportunity to set command line 
 # options and to redirect output.
sys.argv.extend(["--noinc", "--chart"])
sys.stdout = StringIO("")
#sys.stdout = open("output.txt", "w")
import suitename


def test():
  stream = StringIO(data)
  outFile=StringIO("")
  suitename.main(stream, outFile=outFile)

  output = outFile.getvalue()
  if output.strip() == canonicalOutput.strip():
   sys.stderr.write("Success\n")
  else:
   sys.stderr.write("Failed\n")
   sys.stderr.write("========================================\n=")
   sys.stderr.write(canonicalOutput.strip())
   sys.stderr.write("\n\n=========================================\n")
   sys.stderr.write(output.strip())


test()
