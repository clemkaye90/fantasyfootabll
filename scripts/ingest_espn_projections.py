"""One-off ingestion script: parse Mike Clay's 2026 ESPN Projection Guide
(QB/RB/WR/TE positional projection tables) into the committed SQLite
database bundled with the app.

The source is a PDF the user pasted into chat, not a re-fetchable URL or
file on disk — so unlike the other ingestion scripts, the data below is
transcribed directly from that document rather than parsed from a file.
Games (G) is each player's own row, same as CBS/Yahoo.

Note: neither the QB nor the RB/WR/TE tables in this guide include a
fumbles column, so fumbles_lost is left null for every ESPN row (excluded
from that stat's average across sources rather than treated as zero).

Only touches the "ESPN" source rows — see scripts/_shared.py.
"""

import csv
import io

from _shared import name_matcher, write_rows

# name,team,pass_att,pass_cmp,pass_yds,pass_td,pass_int,rush_att,rush_yds,rush_td,games
QB_CSV = """
Josh Allen,BUF,509,340,3946,26,12,116,580,12,17
Lamar Jackson,BLT,467,303,3888,26,10,122,671,4,17
Jalen Hurts,PHI,499,328,3779,24,9,106,438,9,17
Drake Maye,NE,520,355,4096,27,11,101,532,4,17
Jayden Daniels,WAS,519,347,3851,22,10,131,670,5,17
Joe Burrow,CIN,572,387,4132,33,11,52,189,2,17
Jaxson Dart,NYG,504,327,3685,21,10,101,552,7,17
Bo Nix,DEN,564,364,3877,27,11,82,356,4,17
Matthew Stafford,LAR,558,356,4282,35,10,27,39,1,17
Brock Purdy,SF,530,352,4181,27,14,65,277,4,17
Patrick Mahomes,KC,551,358,4001,26,12,53,327,3,17
Trevor Lawrence,JAX,560,347,3933,25,13,73,335,5,17
Dak Prescott,DAL,553,370,4113,30,12,51,186,2,17
Justin Herbert,LAC,527,345,3850,26,11,78,406,2,17
Caleb Williams,CHI,528,317,3821,25,10,71,382,2,17
Jared Goff,DET,544,371,4216,29,10,27,49,1,17
Daniel Jones,IND,529,350,3751,20,11,73,307,6,17
Tyler Shough,NO,545,355,3886,21,11,66,286,4,17
Baker Mayfield,TB,527,339,3824,25,12,54,323,1,17
Jordan Love,GB,531,342,3991,25,11,50,213,1,17
Kyler Murray,MIN,490,331,3347,19,10,71,444,3,17
C.J. Stroud,HST,551,351,3950,22,12,57,249,1,17
Sam Darnold,SEA,513,335,4013,24,12,44,126,1,17
Malik Willis,MIA,505,323,3560,13,10,106,546,3,17
Bryce Young,CAR,540,336,3640,20,12,58,272,2,17
Geno Smith,NYJ,531,361,3815,20,14,58,220,1,17
Cameron Ward,TEN,558,355,3760,17,10,47,201,2,17
Aaron Rodgers,PIT,568,363,3773,20,11,28,100,1,17
Jacoby Brissett,ARZ,517,327,3355,15,9,47,210,1,17
Fernando Mendoza,LV,450,285,3059,14,11,52,226,2,17
Deshaun Watson,CLV,311,191,2040,8,7,42,211,1,17
Tua Tagovailoa,ATL,302,204,2171,10,8,16,44,0,17
Michael Penix Jr.,ATL,265,168,1884,9,5,19,77,1,17
Shedeur Sanders,CLV,232,147,1631,7,6,21,120,1,17
Kirk Cousins,LV,119,79,832,4,3,6,11,0,17
J.J. McCarthy,MIN,86,55,599,3,2,10,44,1,17
Carson Beck,ARZ,66,41,451,3,2,7,29,0,2
Justin Fields,KC,21,13,141,1,0,3,15,0,17
Joe Flacco,CIN,25,15,165,1,1,0,1,0,17
Jarrett Stidham,DEN,22,14,162,1,1,2,7,0,17
"""

# name,team,rush_att,rush_yds,rush_td,rec,rec_yds,rec_td,games
SKILL_CSV = """
Jahmyr Gibbs,DET,283,1373,14,68,546,3,17
Bijan Robinson,ATL,287,1372,8,76,708,3,17
Christian McCaffrey,SF,274,1131,9,79,684,5,17
Jonathan Taylor,IND,325,1500,12,51,390,1,17
De'Von Achane,MIA,258,1308,5,65,511,3,17
Ashton Jeanty,LV,279,1128,7,65,496,2,17
James Cook,BUF,300,1401,11,36,302,2,17
Jeremiyah Love,ARZ,255,1128,7,65,488,2,17
Derrick Henry,BLT,317,1484,13,21,210,1,17
Breece Hall,NYJ,265,1164,8,52,441,3,17
Ken Walker III,KC,277,1239,9,48,376,2,17
Saquon Barkley,PHI,300,1285,9,43,371,2,17
Chase Brown,CIN,238,1038,7,64,435,3,17
Omarion Hampton,LAC,254,1084,9,52,363,2,17
Javonte Williams,DAL,290,1266,11,37,218,2,17
Josh Jacobs,GB,278,1144,12,36,280,2,17
Travis Etienne,NO,260,1130,6,44,381,2,17
Cam Skattebo,NYG,249,1044,7,45,332,1,17
Kyren Williams,LAR,237,1071,10,33,224,2,17
Quinshon Judkins,CLV,317,1245,7,32,221,1,17
D'Andre Swift,CHI,219,994,8,30,269,1,17
Bucky Irving,TB,244,991,5,37,294,2,17
Bhayshul Tuten,JAX,237,994,7,34,250,1,17
Rhamondre Stevenson,NE,174,740,7,43,350,2,17
TreVeyon Henderson,NE,190,837,7,39,268,1,17
Jadarian Price,SEA,223,922,8,27,212,1,17
David Montgomery,HST,215,932,7,31,231,1,17
Jaylen Warren,PIT,180,791,4,46,320,1,17
Rico Dowdle,PIT,223,975,6,29,211,1,17
Tony Pollard,TEN,239,1044,5,30,183,0,17
Kenneth Gainwell,TB,118,521,5,52,342,2,17
Aaron Jones,MIN,150,652,3,47,344,2,17
Kyle Monangai,CHI,192,825,6,26,215,1,17
J.K. Dobbins,DEN,205,958,7,21,132,1,17
Chuba Hubbard,CAR,177,709,4,41,300,1,17
Jonathon Brooks,CAR,193,810,4,33,247,1,17
Rachaad White,WAS,135,568,5,40,267,2,17
Jacory Croskey-Merritt,WAS,196,848,7,16,119,1,17
Blake Corum,LAR,182,837,7,17,117,1,17
Tyjae Spears,TEN,106,447,3,50,336,2,17
Jordan Mason,MIN,194,899,6,13,83,0,17
RJ Harvey,DEN,78,316,3,49,367,3,17
Zach Charbonnet,SEA,137,555,7,20,145,0,11
Woody Marks,HST,143,581,3,24,201,1,17
Alvin Kamara,NO,126,504,2,35,236,1,17
Isiah Pacheco,DET,148,639,5,17,114,1,17
Justice Hill,BLT,49,223,1,39,349,2,17
Samaje Perine,CIN,101,441,3,19,139,1,17
Tyrone Tracy Jr.,NYG,111,472,2,20,146,1,17
Brian Robinson Jr.,ATL,135,560,4,9,59,0,17
Keaton Mitchell,LAC,83,393,2,20,157,1,17
Tyler Allgeier,ARZ,97,385,3,18,126,0,17
Dylan Sampson,CLV,55,228,1,30,207,1,17
MarShawn Lloyd,GB,90,381,3,16,114,1,17
Ty Johnson,BUF,51,219,2,22,208,1,17
Braelon Allen,NYJ,83,348,3,13,91,0,17
Jonah Coleman,DEN,66,272,2,17,127,1,17
Chris Rodriguez,JAX,100,432,3,4,29,0,17
Mike Washington Jr.,LV,88,362,2,8,60,0,17
Tank Bigsby,PHI,83,373,3,4,29,0,17
Emari Demercado,KC,54,256,1,16,108,1,17
Jordan James,SF,75,321,2,8,63,0,17
Jaydon Blue,DAL,62,263,2,9,62,0,17
Isaiah Davis,NYJ,39,178,1,13,96,0,17
Emmett Johnson,KC,50,206,2,8,59,0,17
LeQuint Allen,JAX,8,34,0,22,148,1,17
Kyle Juszczyk,SF,4,19,0,20,162,1,17
Jaylen Wright,MIA,56,234,1,7,56,0,17
George Holani,SEA,39,164,2,8,62,0,17
Ray Davis,BUF,32,138,1,8,60,0,17
Sean Tucker,TB,44,182,2,2,14,0,17
Kimani Vidal,LAC,33,136,1,8,63,0,17
DJ Giddens,IND,33,140,1,8,58,0,17
Chris Brooks,GB,22,98,1,12,83,0,17
Ollie Gordon II,MIA,49,203,1,4,28,0,17
Kaelon Black,SF,35,147,1,4,31,0,17
Phil Mafah,DAL,31,132,1,4,31,0,17
Will Shipley,PHI,9,40,0,11,83,0,17
Adam Randall,BLT,29,121,1,4,29,0,17
Hunter Luepke,DAL,13,57,0,9,62,0,17
Devin Singletary,NYG,22,89,1,4,26,0,17
Nicholas Singleton,TEN,20,84,1,4,30,0,17
Tahj Brooks,CIN,30,128,1,0,0,0,17
Demond Claiborne,MIN,14,59,0,5,29,0,17
Trevor Etienne,CAR,12,52,0,4,29,0,17
Alec Ingold,LAC,2,9,0,8,59,0,17
Kaytron Allen,WAS,12,51,0,4,29,0,17
Seth McGowan,IND,12,52,0,4,30,0,17
Adam Prentice,DEN,4,17,0,4,30,0,17
Connor Heyward,LV,4,17,0,4,29,0,17
Michael Burton,CLV,4,18,0,4,27,0,17
Emanuel Wilson,SEA,11,48,0,1,10,0,6
Max Bredeson,MIN,2,8,0,5,29,0,17
Andrew Beck,NYJ,0,0,0,4,29,0,17
Riley Nowakowski,PIT,0,0,0,4,29,0,17
Reggie Gilliam,NE,0,0,0,4,30,0,17
Patrick Ricard,NYG,0,0,0,4,27,0,17
Kendre Miller,NO,13,55,0,0,0,0,17
Jawhar Jordan,HST,13,54,0,0,0,0,17
Kaleb Johnson,PIT,9,36,0,0,0,0,17
British Brooks,HST,4,18,0,0,0,0,17
Kene Nwangwu,NYJ,0,0,0,0,0,0,17
Isaac Guerendo,SF,0,0,0,0,0,0,17
Brashard Smith,KC,0,0,0,0,0,0,17
Bam Knight,ARZ,0,0,0,0,0,0,17
Dylan Laube,LV,0,0,0,0,0,0,17
Rasheen Ali,BLT,0,0,0,0,0,0,17
Tyler Badie,DEN,0,0,0,0,0,0,17
Jacob Saylors,DET,0,0,0,0,0,0,17
DeeJay Dallas,JAX,0,0,0,0,0,0,17
Josh Williams,TB,0,0,0,0,0,0,17
Puka Nacua,LAR,16,106,1,123,1590,10,17
Ja'Marr Chase,CIN,4,21,0,120,1509,11,17
Jaxon Smith-Njigba,SEA,5,25,0,117,1569,9,17
Amon-Ra St. Brown,DET,2,13,0,118,1426,10,17
Justin Jefferson,MIN,2,11,0,111,1376,7,17
CeeDee Lamb,DAL,2,13,0,103,1375,9,17
Rashee Rice,KC,8,43,1,96,1134,9,17
Drake London,ATL,0,0,0,102,1250,7,17
Chris Olave,NO,0,0,0,91,1198,7,17
Garrett Wilson,NYJ,2,11,0,100,1176,5,17
Nico Collins,HST,2,12,0,86,1212,7,17
A.J. Brown,NE,0,0,0,86,1214,7,17
Malik Nabers,NYG,4,23,0,86,1135,7,17
DeVonta Smith,PHI,0,0,0,91,1130,6,17
Zay Flowers,BLT,10,57,0,82,1172,6,17
George Pickens,DAL,0,0,0,80,1112,8,17
Tetairoa McMillan,CAR,0,0,0,84,1185,6,17
Davante Adams,LAR,0,0,0,68,1016,11,17
Emeka Egbuka,TB,2,12,0,70,1127,7,17
Ladd McConkey,LAC,0,0,0,80,1039,6,17
Tee Higgins,CIN,0,0,0,73,956,8,17
Terry McLaurin,WAS,0,0,0,77,1053,6,17
Jaylen Waddle,DEN,2,12,0,77,994,6,17
Rome Odunze,CHI,0,0,0,59,1029,8,17
DJ Moore,BUF,7,36,0,67,945,7,17
Jameson Williams,DET,7,45,1,64,1026,6,17
Luther Burden III,CHI,9,50,0,75,937,5,17
Courtland Sutton,DEN,0,0,0,69,895,8,17
Carnell Tate,TEN,0,0,0,75,1024,4,17
Michael Pittman Jr.,PIT,0,0,0,88,863,4,17
DK Metcalf,PIT,0,0,0,65,945,6,17
Marvin Harrison Jr.,ARZ,0,0,0,69,954,5,17
Parker Washington,JAX,8,39,0,64,851,5,17
Alec Pierce,IND,0,0,0,61,948,5,17
Christian Watson,GB,2,13,0,55,866,7,17
Matthew Golden,GB,4,25,0,67,870,5,17
Mike Evans,SF,0,0,0,57,903,6,17
Jakobi Meyers,JAX,6,32,0,70,767,5,17
Brian Thomas Jr.,JAX,4,23,0,57,861,5,17
Michael Wilson,ARZ,0,0,0,71,860,3,17
Wan'Dale Robinson,TEN,4,22,0,79,824,2,17
Xavier Worthy,KC,12,76,1,56,789,5,17
Khalil Shakir,BUF,2,13,0,70,765,4,17
Jordan Addison,MIN,2,14,0,60,770,5,17
Jayden Reed,GB,9,65,0,63,727,4,17
Quentin Johnston,LAC,2,11,0,53,778,6,17
Stefon Diggs,WAS,0,0,0,71,726,3,17
Deebo Samuel,SF,22,109,1,52,681,4,17
Josh Downs,IND,2,11,0,70,697,3,17
Chris Godwin,TB,0,0,0,60,701,5,17
Makai Lemon,PHI,0,0,0,53,741,5,17
KC Concepcion,CLV,6,35,0,58,727,3,17
Romeo Doubs,NE,0,0,0,53,666,5,17
Jalen Coker,CAR,0,0,0,61,689,3,17
Rashid Shaheed,SEA,14,87,1,43,647,3,17
Jayden Higgins,HST,0,0,0,55,667,3,17
Denzel Boston,CLV,0,0,0,55,683,3,17
Jerry Jeudy,CLV,0,0,0,51,710,3,17
Tre Tucker,LV,10,57,0,48,658,3,17
Calvin Ridley,TEN,6,32,0,43,678,3,17
Jalen McMillan,TB,4,25,0,47,589,4,17
De'Zhaun Stribling,SF,0,0,0,43,646,4,17
Adonai Mitchell,NYJ,2,11,0,41,618,4,17
Keenan Allen,IND,0,0,0,55,539,3,17
Jalen Nailor,LV,2,11,0,44,607,3,17
Devaughn Vele,NO,0,0,0,50,545,3,17
Rashod Bateman,BLT,0,0,0,38,614,4,17
Malik Washington,MIA,13,78,0,45,479,2,17
Caleb Douglas,MIA,0,0,0,44,590,2,17
Jauan Jennings,MIN,0,0,0,46,486,3,17
Travis Hunter,JAX,2,11,0,42,497,3,17
Germie Bernard,PIT,2,12,0,40,504,3,17
Dontayvion Wicks,PHI,0,0,0,40,518,3,17
Tank Dell,HST,8,45,0,38,462,3,17
Cooper Kupp,SEA,0,0,0,38,472,3,17
Ja'Kobi Lane,BLT,0,0,0,32,485,3,17
Jordyn Tyson,NO,0,0,0,36,484,3,10
Xavier Legette,CAR,2,11,0,36,418,3,17
Jahan Dotson,ATL,0,0,0,35,443,2,17
Tre Harris,LAC,0,0,0,35,411,2,17
Ryan Flournoy,DAL,2,12,0,34,383,3,17
Darius Slayton,NYG,2,12,0,31,439,2,17
Kayshon Boutte,NE,0,0,0,30,414,3,17
Jalen Tolbert,MIA,0,0,0,34,420,2,17
Zachariah Branch,ATL,0,0,0,31,382,2,17
Antonio Williams,WAS,4,22,0,26,344,2,17
Tyquan Thornton,KC,0,0,0,24,359,3,17
Jaylin Noel,HST,4,22,0,29,323,2,17
Keon Coleman,BUF,0,0,0,24,338,3,17
Isaac TeSlaa,DET,0,0,0,24,301,3,17
Pat Bryant,DEN,0,0,0,28,320,2,17
Marvin Mims,DEN,8,45,0,24,273,2,17
Omar Cooper Jr.,NYJ,2,12,0,25,301,2,17
Kavontae Turpin,DAL,18,103,0,18,229,2,17
Jack Bech,LV,0,0,0,28,315,1,17
Tory Horton,SEA,0,0,0,22,299,2,17
Ted Hurst,TB,0,0,0,23,295,2,17
Darnell Mooney,NYG,2,12,0,21,309,2,17
DeMario Douglas,NE,4,21,0,23,271,2,17
Chris Bell,MIA,0,0,0,24,310,1,13
Savion Williams,GB,9,47,0,20,231,2,17
Malachi Fields,NYG,0,0,0,23,279,2,17
Andrei Iosivas,CIN,2,11,0,21,235,2,17
Tutu Atwell,MIA,2,11,0,22,312,0,17
Troy Franklin,DEN,2,11,0,17,216,2,17
Kendrick Bourne,ARZ,0,0,0,23,239,1,17
Malik Benson,LV,0,0,0,19,244,1,17
Kalif Raymond,CHI,5,27,0,19,187,1,17
Dyami Brown,WAS,0,0,0,16,217,2,17
Isaiah Williams,NYJ,2,13,0,19,186,1,17
Treylon Burks,WAS,0,0,0,15,218,1,17
Josh Palmer,BUF,0,0,0,17,205,1,17
Cyrus Allen,KC,0,0,0,16,203,1,17
Devontez Walker,BLT,0,0,0,14,209,1,17
Colbie Young,CIN,0,0,0,14,176,1,17
Bryce Lance,NO,0,0,0,15,193,1,17
Chimere Dike,TEN,10,50,1,11,112,1,17
Jaylin Lane,WAS,0,0,0,12,159,1,17
Christian Kirk,SF,0,0,0,13,176,1,17
Zavion Thomas,CHI,0,0,0,12,154,1,17
Marquise Brown,PHI,0,0,0,12,154,1,17
Xavier Hutchinson,HST,2,12,0,12,152,1,17
Elijah Sarratt,BLT,0,0,0,11,166,1,17
Kevin Coleman Jr.,MIA,0,0,0,13,170,0,17
Olamide Zaccheaus,ATL,0,0,0,14,142,1,17
Jordan Whittington,LAR,2,12,0,11,128,1,17
Isaiah Bond,CLV,4,24,0,10,130,1,17
Ashton Dulin,IND,4,26,0,10,126,1,17
Konata Mumpfield,LAR,0,0,0,10,127,1,17
Roman Wilson,PIT,0,0,0,12,135,1,17
Skyler Bell,BUF,0,0,0,10,137,1,17
Mack Hollins,NE,0,0,0,11,127,1,17
Brenen Thompson,LAC,2,11,0,10,122,1,17
Odell Beckham Jr.,NYG,0,0,0,9,113,1,17
Elic Ayomanor,TEN,0,0,0,9,116,1,17
Kyle T. Williams,NE,4,22,0,6,91,1,17
Tez Johnson,TB,4,23,0,7,78,1,17
Jimmy Horn Jr.,CAR,6,37,0,7,76,0,17
Luke McCaffrey,WAS,0,0,0,7,80,1,17
Jalen Royals,KC,0,0,0,7,78,1,17
KeAndre Lambert-Smith,LAC,0,0,0,6,81,1,17
Mason Tipton,NO,0,0,0,7,81,0,17
Nick Westbrook-Ikhine,IND,0,0,0,6,77,1,17
Dont'e Thornton Jr.,LV,0,0,0,6,83,0,17
Calvin Austin III,NYG,0,0,0,6,74,0,17
Greg Dortch,DET,5,24,0,4,40,0,17
Barion Brown,NO,0,0,0,5,57,0,17
Bo Melton,GB,4,26,0,3,37,0,17
Derius Davis,LAC,2,11,0,3,38,0,17
Xavier Smith,LAR,0,0,0,4,44,0,17
Tyrell Shavers,BUF,0,0,0,4,52,0,11
Mitchell Tinsley,CIN,0,0,0,3,42,0,17
CJ Daniels,LAR,0,0,0,3,43,0,17
Malachi Corley,CLV,6,44,0,2,16,0,17
Demarcus Robinson,SF,0,0,0,3,44,0,17
Tai Felton,MIN,0,0,0,4,37,0,17
Jahdae Walker,CHI,0,0,0,3,36,0,17
Justin Watson,HST,0,0,0,3,42,0,17
Darius Cooper,PHI,0,0,0,3,38,0,17
Jonathan Mingo,DAL,0,0,0,3,41,0,17
Reggie Virgil,ARZ,0,0,0,3,39,0,17
Brycen Tremayne,CAR,0,0,0,3,36,0,17
Cedric Tillman,CLV,0,0,0,3,33,0,17
Kaden Wetjen,PIT,2,12,0,0,0,0,17
Ben Skowronek,PIT,0,0,0,2,17,0,17
Kameron Johnson,TB,2,12,0,0,0,0,17
Arian Smith,NYJ,4,24,0,0,0,0,17
Jalen Reagor,MIA,0,0,0,1,18,0,4
Braxton Berrios,NYG,0,0,0,0,0,0,17
Charlie Jones,CIN,0,0,0,0,0,0,17
Myles Price,MIN,0,0,0,0,0,0,17
LaJohntay Wester,BLT,0,0,0,0,0,0,17
Britain Covey,PHI,0,0,0,0,0,0,17
Nikko Remigio,KC,0,0,0,0,0,0,17
Anthony Gould,IND,0,0,0,0,0,0,17
Jacob Cowing,SF,0,0,0,0,0,0,17
Ke'Shawn Williams,CIN,0,0,0,0,0,0,17
Devin Duvernay,ARZ,0,0,0,0,0,0,17
Gage Larvadain,CLV,0,0,0,0,0,0,17
Efton Chism III,NE,0,0,0,0,0,0,17
Skyy Moore,GB,0,0,0,0,0,0,17
Dareke Young,LV,0,0,0,0,0,0,17
Josh Cameron,JAX,0,0,0,0,0,0,17
Jalen Brooks,ARZ,0,0,0,0,0,0,17
Michael Bandy,DEN,0,0,0,0,0,0,17
Jeshaun Jones,MIN,0,0,0,0,0,0,17
Mason Kinsey,TEN,0,0,0,0,0,0,17
Trey McBride,ARZ,0,0,0,108,1023,5,17
Brock Bowers,LV,4,15,0,99,999,7,17
Tyler Warren,IND,6,14,0,85,894,6,17
Colston Loveland,CHI,0,0,0,80,897,6,17
Sam LaPorta,DET,0,0,0,78,787,5,17
Harold Fannin Jr.,CLV,9,21,0,83,819,3,17
Kyle Pitts,ATL,0,0,0,80,858,3,17
Tucker Kraft,GB,2,8,0,71,818,4,17
Travis Kelce,KC,0,0,0,74,771,5,17
Dallas Goedert,PHI,0,0,0,71,726,6,17
George Kittle,SF,0,0,0,70,760,5,15
Mark Andrews,BLT,10,35,1,58,618,7,17
Jake Ferguson,DAL,0,0,0,73,598,6,17
T.J. Hockenson,MIN,0,0,0,78,639,3,17
Isaiah Likely,NYG,0,0,0,63,683,4,17
Dalton Kincaid,BUF,0,0,0,59,697,4,17
Kenyon Sadiq,NYJ,0,0,0,63,657,4,17
Hunter Henry,NE,0,0,0,56,628,5,17
Juwan Johnson,NO,0,0,0,63,645,3,17
Brenton Strange,JAX,0,0,0,59,599,4,17
Pat Freiermuth,PIT,0,0,0,60,603,3,17
Terrance Ferguson,LAR,0,0,0,46,580,5,17
Dalton Schultz,HST,0,0,0,59,556,3,17
Gunnar Helm,TEN,0,0,0,58,499,3,17
Chigoziem Okonkwo,WAS,0,0,0,51,560,2,17
Greg Dulcich,MIA,0,0,0,52,580,2,17
Darren Waller,CAR,0,0,0,43,473,4,17
A.J. Barner,SEA,9,18,0,45,433,4,17
Evan Engram,DEN,0,0,0,47,465,2,17
David Njoku,LAC,0,0,0,40,417,4,17
Cade Otton,TB,0,0,0,45,440,2,17
Mike Gesicki,CIN,0,0,0,32,313,4,17
Michael Mayer,LV,0,0,0,37,364,1,17
Oronde Gadsden II,LAC,0,0,0,30,322,3,17
Colby Parkinson,LAR,0,0,0,28,292,3,17
Darnell Washington,PIT,0,0,0,31,305,2,17
Dawson Knox,BUF,0,0,0,25,265,3,17
Mason Taylor,NYJ,0,0,0,31,269,1,17
Theo Johnson,NYG,0,0,0,25,269,2,17
Noah Gray,KC,0,0,0,26,262,1,17
Elijah Arroyo,SEA,0,0,0,24,264,2,17
Erick All,CIN,0,0,0,26,235,2,17
Cole Kmet,CHI,0,0,0,22,219,2,17
Tommy Tremble,CAR,0,0,0,18,177,1,17
Austin Hooper,ATL,0,0,0,21,181,1,17
Elijah Higgins,ARZ,0,0,0,21,182,1,17
Ja'Tavion Sanders,CAR,0,0,0,20,164,1,17
Will Kacmarek,MIA,0,0,0,18,174,1,17
Drew Sample,CIN,0,0,0,17,146,1,17
Josh Oliver,MIN,0,0,0,17,151,1,17
Tyler Higbee,LAR,0,0,0,15,154,1,17
Eli Raridon,NE,0,0,0,16,151,1,17
Charlie Kolar,LAC,0,0,0,15,149,1,17
Noah Fant,NO,0,0,0,17,145,1,17
Cade Stover,HST,4,10,0,15,134,1,17
John Bates,WAS,0,0,0,14,136,1,17
Jake Tonges,SF,0,0,0,13,135,1,17
Tanner Hudson,CIN,0,0,0,13,110,1,17
Eli Stowers,PHI,5,20,0,11,107,1,17
Adam Trautman,DEN,0,0,0,12,113,1,17
Luke Schoonmaker,DAL,0,0,0,11,110,1,17
Mo Alie-Cox,IND,0,0,0,11,114,1,17
Jackson Hawes,BUF,0,0,0,11,110,1,17
Daniel Bellinger,TEN,0,0,0,13,113,0,17
Ben Sinnott,WAS,0,0,0,11,107,1,17
Jeremy Ruckert,NYJ,0,0,0,12,97,1,17
Durham Smythe,BLT,0,0,0,10,94,1,17
Davis Allen,LAR,0,0,0,8,74,1,17
Foster Moreau,HST,0,0,0,8,79,1,17
Nate Adkins,DEN,0,0,0,8,69,1,17
Brock Wright,DET,0,0,0,8,72,1,17
Nate Boerkircher,JAX,0,0,0,8,74,1,17
Payne Durham,TB,0,0,0,7,71,1,17
Oscar Delp,NO,0,0,0,8,74,0,17
Joe Royer,CLV,0,0,0,8,67,0,17
Luke Musgrave,GB,0,0,0,7,67,0,17
Ben Sims,MIA,0,0,0,7,65,0,17
Luke Farrell,SF,0,0,0,4,41,0,17
Max Klare,LAR,0,0,0,4,38,0,17
Justin Joly,DEN,0,0,0,4,38,0,17
"""


def _parse_qb(match_name) -> list[dict]:
    out = []
    reader = csv.reader(io.StringIO(QB_CSV.strip()))
    for row in reader:
        name, team, pass_att, pass_cmp, pass_yds, pass_td, pass_int, rush_att, rush_yds, rush_td, games = row
        gsis_id = match_name(name)
        if gsis_id is None:
            continue
        out.append({
            "source": "ESPN", "gsis_id": gsis_id, "name": name, "games": int(games),
            "pass_att": int(pass_att), "pass_cmp": int(pass_cmp), "pass_yds": int(pass_yds),
            "pass_td": int(pass_td), "pass_int": int(pass_int),
            "rush_att": int(rush_att), "rush_yds": int(rush_yds), "rush_td": int(rush_td),
            "rec": None, "rec_yds": None, "rec_td": None,
            "fumbles_lost": None,
        })
    return out


def _parse_skill(match_name) -> list[dict]:
    out = []
    reader = csv.reader(io.StringIO(SKILL_CSV.strip()))
    for row in reader:
        name, team, rush_att, rush_yds, rush_td, rec, rec_yds, rec_td, games = row
        gsis_id = match_name(name)
        if gsis_id is None:
            continue
        out.append({
            "source": "ESPN", "gsis_id": gsis_id, "name": name, "games": int(games),
            "pass_att": None, "pass_cmp": None, "pass_yds": None, "pass_td": None, "pass_int": None,
            "rush_att": int(rush_att), "rush_yds": int(rush_yds), "rush_td": int(rush_td),
            "rec": int(rec), "rec_yds": int(rec_yds), "rec_td": int(rec_td),
            "fumbles_lost": None,
        })
    return out


def main() -> None:
    match_name = name_matcher()
    rows = _parse_qb(match_name) + _parse_skill(match_name)
    write_rows(rows, sources=["ESPN"])


if __name__ == "__main__":
    main()
