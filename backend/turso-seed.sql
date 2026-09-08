BEGIN TRANSACTION;
CREATE TABLE achievements (
	id INTEGER NOT NULL, 
	"key" VARCHAR(48) NOT NULL, 
	title VARCHAR(80) NOT NULL, 
	description TEXT NOT NULL, 
	icon VARCHAR(32) NOT NULL, 
	color_key VARCHAR(24) NOT NULL, 
	order_index INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE ("key")
);
INSERT INTO "achievements" VALUES(1,'FIRST_LESSON','First steps','Complete your first lesson','star','green',0);
INSERT INTO "achievements" VALUES(2,'PERFECT_LESSON','Flawless','Complete a lesson without a single mistake','target','blue',1);
INSERT INTO "achievements" VALUES(3,'FIRST_SKILL','Crowned','Earn your first crown by finishing every lesson in a skill','crown','gold',2);
INSERT INTO "achievements" VALUES(4,'XP_100','Century','Earn 100 XP in total','bolt','gold',3);
INSERT INTO "achievements" VALUES(5,'STREAK_3','On a roll','Reach a 3-day streak','flame','orange',4);
INSERT INTO "achievements" VALUES(6,'STREAK_7','Unstoppable','Reach a 7-day streak','flame','purple',5);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('0001');
CREATE TABLE courses (
	id INTEGER NOT NULL, 
	slug VARCHAR(64) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	source_language VARCHAR(40) NOT NULL, 
	target_language VARCHAR(40) NOT NULL, 
	flag_emoji VARCHAR(8) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
);
INSERT INTO "courses" VALUES(1,'spanish-for-english-speakers','Spanish','Learn everyday Spanish from English, one short lesson at a time.','English','Spanish','🇪🇸','2026-09-08 07:54:42.520988');
CREATE TABLE exercises (
	id INTEGER NOT NULL, 
	lesson_id INTEGER NOT NULL, 
	type VARCHAR(24) NOT NULL, 
	order_index INTEGER NOT NULL, 
	instruction VARCHAR(120) NOT NULL, 
	prompt TEXT NOT NULL, 
	data JSON NOT NULL, 
	correct_answer JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE CASCADE, 
	CONSTRAINT uq_exercise_order_in_lesson UNIQUE (lesson_id, order_index), 
	CONSTRAINT ck_exercise_type CHECK (type IN ('MULTIPLE_CHOICE', 'TRANSLATE', 'MATCH_PAIRS', 'FILL_BLANK', 'TYPE_ANSWER'))
);
INSERT INTO "exercises" VALUES(1,1,'MULTIPLE_CHOICE',0,'Select the correct translation','Hello','{"options": [{"id": "o1", "text": "Hola"}, {"id": "o2", "text": "Adi\u00f3s"}, {"id": "o3", "text": "Gracias"}, {"id": "o4", "text": "Noche"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(2,1,'TRANSLATE',1,'Translate this sentence','Good morning','{"tokens": ["buenos", "d\u00edas", "hola", "noches", "tardes"]}','{"accepted": ["buenos d\u00edas"]}');
INSERT INTO "exercises" VALUES(3,1,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "hola"}, {"id": "l2", "text": "adi\u00f3s"}, {"id": "l3", "text": "buenas noches"}], "right": [{"id": "r1", "text": "good night"}, {"id": "r2", "text": "goodbye"}, {"id": "r3", "text": "hello"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(4,1,'FILL_BLANK',3,'Fill in the blank','Complete the greeting','{"sentence": "___ d\u00edas, se\u00f1ora.", "options": ["Buenos", "Buenas", "Bueno"]}','{"accepted": ["Buenos"]}');
INSERT INTO "exercises" VALUES(5,1,'TYPE_ANSWER',4,'Type this in Spanish','Goodbye','{"language": "es"}','{"accepted": ["adi\u00f3s", "adios"]}');
INSERT INTO "exercises" VALUES(6,2,'MULTIPLE_CHOICE',0,'Select the correct translation','Thank you','{"options": [{"id": "o1", "text": "Gracias"}, {"id": "o2", "text": "Por favor"}, {"id": "o3", "text": "Perd\u00f3n"}, {"id": "o4", "text": "Hola"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(7,2,'TRANSLATE',1,'Translate this sentence','Thank you very much','{"tokens": ["buenas", "favor", "gracias", "muchas", "por"]}','{"accepted": ["muchas gracias"]}');
INSERT INTO "exercises" VALUES(8,2,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "gracias"}, {"id": "l2", "text": "por favor"}, {"id": "l3", "text": "de nada"}], "right": [{"id": "r1", "text": "you''re welcome"}, {"id": "r2", "text": "please"}, {"id": "r3", "text": "thank you"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(9,2,'FILL_BLANK',3,'Fill in the blank','Complete the polite request','{"sentence": "Un caf\u00e9, por ___.", "options": ["favor", "gracias", "nada"]}','{"accepted": ["favor"]}');
INSERT INTO "exercises" VALUES(10,2,'TYPE_ANSWER',4,'Type this in Spanish','Please','{"language": "es"}','{"accepted": ["por favor"]}');
INSERT INTO "exercises" VALUES(11,3,'MULTIPLE_CHOICE',0,'Select the correct translation','My name is Ana','{"options": [{"id": "o1", "text": "Me llamo Ana"}, {"id": "o2", "text": "Tengo Ana"}, {"id": "o3", "text": "Soy de Ana"}, {"id": "o4", "text": "Ana est\u00e1"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(12,3,'TRANSLATE',1,'Translate this sentence','I am a student','{"tokens": ["eres", "estudiante", "maestro", "soy", "un"]}','{"accepted": ["soy estudiante"]}');
INSERT INTO "exercises" VALUES(13,3,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "me llamo"}, {"id": "l2", "text": "soy"}, {"id": "l3", "text": "mucho gusto"}], "right": [{"id": "r1", "text": "nice to meet you"}, {"id": "r2", "text": "I am"}, {"id": "r3", "text": "my name is"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(14,3,'FILL_BLANK',3,'Fill in the blank','Complete the introduction','{"sentence": "Yo ___ llamo Carlos.", "options": ["me", "te", "se"]}','{"accepted": ["me"]}');
INSERT INTO "exercises" VALUES(15,3,'TYPE_ANSWER',4,'Type this in Spanish','Nice to meet you','{"language": "es"}','{"accepted": ["mucho gusto"]}');
INSERT INTO "exercises" VALUES(16,4,'MULTIPLE_CHOICE',0,'Select the correct translation','How are you?','{"options": [{"id": "o1", "text": "\u00bfC\u00f3mo est\u00e1s?"}, {"id": "o2", "text": "\u00bfD\u00f3nde est\u00e1s?"}, {"id": "o3", "text": "\u00bfQu\u00e9 comes?"}, {"id": "o4", "text": "\u00bfQui\u00e9n eres?"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(17,4,'TRANSLATE',1,'Translate this sentence','I am very well','{"tokens": ["bien", "eres", "estoy", "mal", "muy", "poco"]}','{"accepted": ["estoy muy bien"]}');
INSERT INTO "exercises" VALUES(18,4,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "bien"}, {"id": "l2", "text": "mal"}, {"id": "l3", "text": "m\u00e1s o menos"}], "right": [{"id": "r1", "text": "so-so"}, {"id": "r2", "text": "badly"}, {"id": "r3", "text": "well"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(19,4,'FILL_BLANK',3,'Fill in the blank','Complete the polite question','{"sentence": "\u00bfC\u00f3mo ___ usted?", "options": ["est\u00e1", "est\u00e1s", "estoy"]}','{"accepted": ["est\u00e1"]}');
INSERT INTO "exercises" VALUES(20,4,'TYPE_ANSWER',4,'Type this in Spanish','And you?','{"language": "es"}','{"accepted": ["\u00bfy t\u00fa?", "y t\u00fa", "y usted"]}');
INSERT INTO "exercises" VALUES(21,5,'MULTIPLE_CHOICE',0,'Select the correct translation','Yes','{"options": [{"id": "o1", "text": "S\u00ed"}, {"id": "o2", "text": "No"}, {"id": "o3", "text": "Tal vez"}, {"id": "o4", "text": "Nunca"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(22,5,'TRANSLATE',1,'Translate this sentence','I do not understand','{"tokens": ["entiendo", "hablo", "mucho", "no", "s\u00ed"]}','{"accepted": ["no entiendo"]}');
INSERT INTO "exercises" VALUES(23,5,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "s\u00ed"}, {"id": "l2", "text": "no"}, {"id": "l3", "text": "tal vez"}], "right": [{"id": "r1", "text": "maybe"}, {"id": "r2", "text": "no"}, {"id": "r3", "text": "yes"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(24,5,'FILL_BLANK',3,'Fill in the blank','Complete the answer','{"sentence": "___, no hablo espa\u00f1ol.", "options": ["No", "S\u00ed", "Ya"]}','{"accepted": ["No"]}');
INSERT INTO "exercises" VALUES(25,5,'TYPE_ANSWER',4,'Type this in Spanish','I don''t know','{"language": "es"}','{"accepted": ["no s\u00e9", "no se"]}');
INSERT INTO "exercises" VALUES(26,6,'MULTIPLE_CHOICE',0,'Select the correct translation','Where is the bathroom?','{"options": [{"id": "o1", "text": "\u00bfD\u00f3nde est\u00e1 el ba\u00f1o?"}, {"id": "o2", "text": "\u00bfQu\u00e9 es el ba\u00f1o?"}, {"id": "o3", "text": "\u00bfC\u00f3mo es el ba\u00f1o?"}, {"id": "o4", "text": "\u00bfCu\u00e1ndo es el ba\u00f1o?"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(27,6,'TRANSLATE',1,'Translate this sentence','What is this','{"tokens": ["c\u00f3mo", "d\u00f3nde", "es", "ese", "esto", "qu\u00e9"]}','{"accepted": ["qu\u00e9 es esto"]}');
INSERT INTO "exercises" VALUES(28,6,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "d\u00f3nde"}, {"id": "l2", "text": "qu\u00e9"}, {"id": "l3", "text": "cu\u00e1ndo"}], "right": [{"id": "r1", "text": "when"}, {"id": "r2", "text": "what"}, {"id": "r3", "text": "where"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(29,6,'FILL_BLANK',3,'Fill in the blank','Complete the question','{"sentence": "\u00bf___ est\u00e1 la estaci\u00f3n?", "options": ["D\u00f3nde", "Qu\u00e9", "C\u00f3mo"]}','{"accepted": ["D\u00f3nde"]}');
INSERT INTO "exercises" VALUES(30,6,'TYPE_ANSWER',4,'Type this in Spanish','Who?','{"language": "es"}','{"accepted": ["\u00bfqui\u00e9n?", "qui\u00e9n", "quien"]}');
INSERT INTO "exercises" VALUES(31,7,'MULTIPLE_CHOICE',0,'Select the correct translation','Water','{"options": [{"id": "o1", "text": "El agua"}, {"id": "o2", "text": "El pan"}, {"id": "o3", "text": "La leche"}, {"id": "o4", "text": "El caf\u00e9"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(32,7,'TRANSLATE',1,'Translate this sentence','I drink coffee','{"tokens": ["bebo", "caf\u00e9", "come", "leche", "t\u00fa", "yo"]}','{"accepted": ["yo bebo caf\u00e9"]}');
INSERT INTO "exercises" VALUES(33,7,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "el agua"}, {"id": "l2", "text": "la leche"}, {"id": "l3", "text": "el caf\u00e9"}], "right": [{"id": "r1", "text": "coffee"}, {"id": "r2", "text": "milk"}, {"id": "r3", "text": "water"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(34,7,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "Yo ___ agua todos los d\u00edas.", "options": ["bebo", "como", "hablo"]}','{"accepted": ["bebo"]}');
INSERT INTO "exercises" VALUES(35,7,'TYPE_ANSWER',4,'Type this in Spanish','The milk','{"language": "es"}','{"accepted": ["la leche", "leche"]}');
INSERT INTO "exercises" VALUES(36,8,'MULTIPLE_CHOICE',0,'Select the correct translation','The bread','{"options": [{"id": "o1", "text": "El pan"}, {"id": "o2", "text": "La manzana"}, {"id": "o3", "text": "El queso"}, {"id": "o4", "text": "La sopa"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(37,8,'TRANSLATE',1,'Translate this sentence','I want an apple','{"tokens": ["comes", "el", "manzana", "pan", "quiero", "una"]}','{"accepted": ["quiero una manzana"]}');
INSERT INTO "exercises" VALUES(38,8,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "el pan"}, {"id": "l2", "text": "la manzana"}, {"id": "l3", "text": "el queso"}], "right": [{"id": "r1", "text": "cheese"}, {"id": "r2", "text": "apple"}, {"id": "r3", "text": "bread"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(39,8,'FILL_BLANK',3,'Fill in the blank','Complete the request','{"sentence": "Una mesa ___ dos personas.", "options": ["para", "por", "con"]}','{"accepted": ["para"]}');
INSERT INTO "exercises" VALUES(40,8,'TYPE_ANSWER',4,'Type this in Spanish','I am hungry','{"language": "es"}','{"accepted": ["tengo hambre", "yo tengo hambre"]}');
INSERT INTO "exercises" VALUES(41,9,'MULTIPLE_CHOICE',0,'Select the correct translation','The mother','{"options": [{"id": "o1", "text": "La madre"}, {"id": "o2", "text": "El padre"}, {"id": "o3", "text": "La hija"}, {"id": "o4", "text": "El hijo"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(42,9,'TRANSLATE',1,'Translate this sentence','My father is tall','{"tokens": ["alto", "baja", "es", "madre", "mi", "padre", "son"]}','{"accepted": ["mi padre es alto"]}');
INSERT INTO "exercises" VALUES(43,9,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "la madre"}, {"id": "l2", "text": "el padre"}, {"id": "l3", "text": "los padres"}], "right": [{"id": "r1", "text": "parents"}, {"id": "r2", "text": "father"}, {"id": "r3", "text": "mother"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(44,9,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "___ madre se llama Elena.", "options": ["Mi", "Tu", "Su"]}','{"accepted": ["Mi"]}');
INSERT INTO "exercises" VALUES(45,9,'TYPE_ANSWER',4,'Type this in Spanish','My family','{"language": "es"}','{"accepted": ["mi familia"]}');
INSERT INTO "exercises" VALUES(46,10,'MULTIPLE_CHOICE',0,'Select the correct translation','The sister','{"options": [{"id": "o1", "text": "La hermana"}, {"id": "o2", "text": "El hermano"}, {"id": "o3", "text": "La abuela"}, {"id": "o4", "text": "El primo"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(47,10,'TRANSLATE',1,'Translate this sentence','I have two brothers','{"tokens": ["dos", "eres", "hermanas", "hermanos", "tengo", "tres"]}','{"accepted": ["tengo dos hermanos"]}');
INSERT INTO "exercises" VALUES(48,10,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "el hermano"}, {"id": "l2", "text": "la hermana"}, {"id": "l3", "text": "el abuelo"}], "right": [{"id": "r1", "text": "grandfather"}, {"id": "r2", "text": "sister"}, {"id": "r3", "text": "brother"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(49,10,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "Mi hermana ___ estudiante.", "options": ["es", "est\u00e1", "son"]}','{"accepted": ["es"]}');
INSERT INTO "exercises" VALUES(50,10,'TYPE_ANSWER',4,'Type this in Spanish','The grandmother','{"language": "es"}','{"accepted": ["la abuela", "abuela"]}');
INSERT INTO "exercises" VALUES(51,11,'MULTIPLE_CHOICE',0,'Select the correct translation','The dog','{"options": [{"id": "o1", "text": "El perro"}, {"id": "o2", "text": "El gato"}, {"id": "o3", "text": "El p\u00e1jaro"}, {"id": "o4", "text": "El pez"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(52,11,'TRANSLATE',1,'Translate this sentence','The cat is small','{"tokens": ["el", "es", "gato", "grande", "la", "peque\u00f1o", "perro"]}','{"accepted": ["el gato es peque\u00f1o"]}');
INSERT INTO "exercises" VALUES(53,11,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "el gato"}, {"id": "l2", "text": "el perro"}, {"id": "l3", "text": "el pez"}], "right": [{"id": "r1", "text": "fish"}, {"id": "r2", "text": "dog"}, {"id": "r3", "text": "cat"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(54,11,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "Mi ___ come mucho.", "options": ["perro", "pan", "padre"]}','{"accepted": ["perro"]}');
INSERT INTO "exercises" VALUES(55,11,'TYPE_ANSWER',4,'Type this in Spanish','A bird','{"language": "es"}','{"accepted": ["un p\u00e1jaro", "un pajaro", "p\u00e1jaro"]}');
INSERT INTO "exercises" VALUES(56,12,'MULTIPLE_CHOICE',0,'Select the correct translation','The horse','{"options": [{"id": "o1", "text": "El caballo"}, {"id": "o2", "text": "La vaca"}, {"id": "o3", "text": "El pollo"}, {"id": "o4", "text": "El cerdo"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(57,12,'TRANSLATE',1,'Translate this sentence','The cow drinks water','{"tokens": ["agua", "bebe", "come", "el", "la", "leche", "vaca"]}','{"accepted": ["la vaca bebe agua"]}');
INSERT INTO "exercises" VALUES(58,12,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "el caballo"}, {"id": "l2", "text": "la vaca"}, {"id": "l3", "text": "el pollo"}], "right": [{"id": "r1", "text": "chicken"}, {"id": "r2", "text": "cow"}, {"id": "r3", "text": "horse"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(59,12,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "El caballo ___ grande.", "options": ["es", "son", "est\u00e1"]}','{"accepted": ["es"]}');
INSERT INTO "exercises" VALUES(60,12,'TYPE_ANSWER',4,'Type this in Spanish','The animals','{"language": "es"}','{"accepted": ["los animales", "animales"]}');
INSERT INTO "exercises" VALUES(61,13,'MULTIPLE_CHOICE',0,'Select the correct translation','Three','{"options": [{"id": "o1", "text": "Tres"}, {"id": "o2", "text": "Dos"}, {"id": "o3", "text": "Cuatro"}, {"id": "o4", "text": "Cinco"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(62,13,'TRANSLATE',1,'Translate this sentence','I have two dogs','{"tokens": ["dos", "eres", "gatos", "perros", "tengo", "tres"]}','{"accepted": ["tengo dos perros"]}');
INSERT INTO "exercises" VALUES(63,13,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "uno"}, {"id": "l2", "text": "dos"}, {"id": "l3", "text": "tres"}], "right": [{"id": "r1", "text": "three"}, {"id": "r2", "text": "two"}, {"id": "r3", "text": "one"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(64,13,'FILL_BLANK',3,'Fill in the blank','Complete the sequence','{"sentence": "Uno, dos, ___, cuatro.", "options": ["tres", "cinco", "seis"]}','{"accepted": ["tres"]}');
INSERT INTO "exercises" VALUES(65,13,'TYPE_ANSWER',4,'Type this in Spanish','Five','{"language": "es"}','{"accepted": ["cinco"]}');
INSERT INTO "exercises" VALUES(66,14,'MULTIPLE_CHOICE',0,'Select the correct translation','Ten','{"options": [{"id": "o1", "text": "Diez"}, {"id": "o2", "text": "Nueve"}, {"id": "o3", "text": "Ocho"}, {"id": "o4", "text": "Siete"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(67,14,'TRANSLATE',1,'Translate this sentence','There are eight books','{"tokens": ["es", "hay", "libros", "mesas", "ocho", "siete"]}','{"accepted": ["hay ocho libros"]}');
INSERT INTO "exercises" VALUES(68,14,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "seis"}, {"id": "l2", "text": "ocho"}, {"id": "l3", "text": "diez"}], "right": [{"id": "r1", "text": "ten"}, {"id": "r2", "text": "eight"}, {"id": "r3", "text": "six"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(69,14,'FILL_BLANK',3,'Fill in the blank','Complete the sequence','{"sentence": "Siete, ocho, ___, diez.", "options": ["nueve", "seis", "cuatro"]}','{"accepted": ["nueve"]}');
INSERT INTO "exercises" VALUES(70,14,'TYPE_ANSWER',4,'Type this in Spanish','Seven','{"language": "es"}','{"accepted": ["siete"]}');
INSERT INTO "exercises" VALUES(71,15,'MULTIPLE_CHOICE',0,'Select the correct translation','To eat','{"options": [{"id": "o1", "text": "Comer"}, {"id": "o2", "text": "Beber"}, {"id": "o3", "text": "Hablar"}, {"id": "o4", "text": "Vivir"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(72,15,'TRANSLATE',1,'Translate this sentence','We speak Spanish','{"tokens": ["ellos", "espa\u00f1ol", "hablamos", "hablo", "ingl\u00e9s"]}','{"accepted": ["hablamos espa\u00f1ol"]}');
INSERT INTO "exercises" VALUES(73,15,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "comer"}, {"id": "l2", "text": "beber"}, {"id": "l3", "text": "hablar"}], "right": [{"id": "r1", "text": "to speak"}, {"id": "r2", "text": "to drink"}, {"id": "r3", "text": "to eat"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(74,15,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "Nosotros ___ pan.", "options": ["comemos", "como", "comen"]}','{"accepted": ["comemos"]}');
INSERT INTO "exercises" VALUES(75,15,'TYPE_ANSWER',4,'Type this in Spanish','I live in Madrid','{"language": "es"}','{"accepted": ["vivo en madrid"]}');
INSERT INTO "exercises" VALUES(76,16,'MULTIPLE_CHOICE',0,'Select the correct translation','I have','{"options": [{"id": "o1", "text": "Tengo"}, {"id": "o2", "text": "Tienes"}, {"id": "o3", "text": "Tiene"}, {"id": "o4", "text": "Tenemos"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(77,16,'TRANSLATE',1,'Translate this sentence','She is my friend','{"tokens": ["amiga", "amigo", "ella", "es", "est\u00e1", "mi", "\u00e9l"]}','{"accepted": ["ella es mi amiga"]}');
INSERT INTO "exercises" VALUES(78,16,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "tengo"}, {"id": "l2", "text": "tienes"}, {"id": "l3", "text": "tenemos"}], "right": [{"id": "r1", "text": "we have"}, {"id": "r2", "text": "you have"}, {"id": "r3", "text": "I have"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(79,16,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "Ellos ___ un gato.", "options": ["tienen", "tengo", "tienes"]}','{"accepted": ["tienen"]}');
INSERT INTO "exercises" VALUES(80,16,'TYPE_ANSWER',4,'Type this in Spanish','We are friends','{"language": "es"}','{"accepted": ["somos amigos"]}');
INSERT INTO "exercises" VALUES(81,17,'MULTIPLE_CHOICE',0,'Select the correct translation','The boy eats bread','{"options": [{"id": "o1", "text": "El ni\u00f1o come pan"}, {"id": "o2", "text": "El ni\u00f1o bebe pan"}, {"id": "o3", "text": "La ni\u00f1a come pan"}, {"id": "o4", "text": "El ni\u00f1o come agua"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(82,17,'TRANSLATE',1,'Translate this sentence','The girl drinks milk','{"tokens": ["agua", "bebe", "come", "el", "la", "leche", "ni\u00f1a"]}','{"accepted": ["la ni\u00f1a bebe leche"]}');
INSERT INTO "exercises" VALUES(83,17,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "el ni\u00f1o"}, {"id": "l2", "text": "la ni\u00f1a"}, {"id": "l3", "text": "la casa"}], "right": [{"id": "r1", "text": "the house"}, {"id": "r2", "text": "the girl"}, {"id": "r3", "text": "the boy"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(84,17,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "La ni\u00f1a ___ en casa.", "options": ["vive", "vives", "vivo"]}','{"accepted": ["vive"]}');
INSERT INTO "exercises" VALUES(85,17,'TYPE_ANSWER',4,'Type this in Spanish','I eat an apple','{"language": "es"}','{"accepted": ["como una manzana"]}');
INSERT INTO "exercises" VALUES(86,18,'MULTIPLE_CHOICE',0,'Select the correct translation','My sister has a cat','{"options": [{"id": "o1", "text": "Mi hermana tiene un gato"}, {"id": "o2", "text": "Mi hermano tiene un gato"}, {"id": "o3", "text": "Mi hermana come un gato"}, {"id": "o4", "text": "Mi hermana tiene un perro"}]}','{"option_id": "o1"}');
INSERT INTO "exercises" VALUES(87,18,'TRANSLATE',1,'Translate this sentence','We drink water at home','{"tokens": ["agua", "bebemos", "casa", "comemos", "en", "la", "leche"]}','{"accepted": ["bebemos agua en casa"]}');
INSERT INTO "exercises" VALUES(88,18,'MATCH_PAIRS',2,'Match the pairs','Match each Spanish word to its meaning','{"left": [{"id": "l1", "text": "en casa"}, {"id": "l2", "text": "todos los d\u00edas"}, {"id": "l3", "text": "por la ma\u00f1ana"}], "right": [{"id": "r1", "text": "in the morning"}, {"id": "r2", "text": "every day"}, {"id": "r3", "text": "at home"}]}','{"pairs": [["l1", "r3"], ["l2", "r2"], ["l3", "r1"]]}');
INSERT INTO "exercises" VALUES(89,18,'FILL_BLANK',3,'Fill in the blank','Complete the sentence','{"sentence": "Mi padre ___ caf\u00e9 por la ma\u00f1ana.", "options": ["bebe", "bebo", "beben"]}','{"accepted": ["bebe"]}');
INSERT INTO "exercises" VALUES(90,18,'TYPE_ANSWER',4,'Type this in Spanish','Good night, see you tomorrow','{"language": "es"}','{"accepted": ["buenas noches, hasta ma\u00f1ana", "buenas noches hasta ma\u00f1ana"]}');
CREATE TABLE lesson_attempt_answers (
	id INTEGER NOT NULL, 
	attempt_id INTEGER NOT NULL, 
	exercise_id INTEGER NOT NULL, 
	submitted JSON NOT NULL, 
	is_correct BOOLEAN NOT NULL, 
	xp_earned INTEGER NOT NULL, 
	hearts_lost INTEGER NOT NULL, 
	answered_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(attempt_id) REFERENCES lesson_attempts (id) ON DELETE CASCADE, 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE CASCADE, 
	CONSTRAINT uq_answer_attempt_exercise UNIQUE (attempt_id, exercise_id)
);
CREATE TABLE lesson_attempt_pairs (
	id INTEGER NOT NULL, 
	attempt_id INTEGER NOT NULL, 
	exercise_id INTEGER NOT NULL, 
	left_id VARCHAR(32) NOT NULL, 
	right_id VARCHAR(32) NOT NULL, 
	is_correct BOOLEAN NOT NULL, 
	hearts_lost INTEGER NOT NULL, 
	answered_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(attempt_id) REFERENCES lesson_attempts (id) ON DELETE CASCADE, 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE CASCADE, 
	CONSTRAINT uq_pair_attempt_exercise_pair UNIQUE (attempt_id, exercise_id, left_id, right_id)
);
CREATE TABLE lesson_attempts (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	lesson_id INTEGER NOT NULL, 
	started_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	completed BOOLEAN NOT NULL, 
	correct_answers INTEGER NOT NULL, 
	incorrect_answers INTEGER NOT NULL, 
	xp_earned INTEGER NOT NULL, 
	hearts_lost INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE lessons (
	id INTEGER NOT NULL, 
	skill_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	order_index INTEGER NOT NULL, 
	xp_reward INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE, 
	CONSTRAINT uq_lesson_order_in_skill UNIQUE (skill_id, order_index)
);
INSERT INTO "lessons" VALUES(1,1,'Hello and goodbye',0,10);
INSERT INTO "lessons" VALUES(2,1,'Polite words',1,10);
INSERT INTO "lessons" VALUES(3,2,'My name is',0,10);
INSERT INTO "lessons" VALUES(4,2,'How are you?',1,10);
INSERT INTO "lessons" VALUES(5,3,'Yes and no',0,10);
INSERT INTO "lessons" VALUES(6,3,'Simple questions',1,10);
INSERT INTO "lessons" VALUES(7,4,'Drinks',0,10);
INSERT INTO "lessons" VALUES(8,4,'At the table',1,10);
INSERT INTO "lessons" VALUES(9,5,'Parents',0,10);
INSERT INTO "lessons" VALUES(10,5,'Brothers and sisters',1,10);
INSERT INTO "lessons" VALUES(11,6,'Pets',0,10);
INSERT INTO "lessons" VALUES(12,6,'On the farm',1,10);
INSERT INTO "lessons" VALUES(13,7,'One to five',0,10);
INSERT INTO "lessons" VALUES(14,7,'Six to ten',1,10);
INSERT INTO "lessons" VALUES(15,8,'Everyday actions',0,10);
INSERT INTO "lessons" VALUES(16,8,'To have and to be',1,10);
INSERT INTO "lessons" VALUES(17,9,'Everyday sentences',0,10);
INSERT INTO "lessons" VALUES(18,9,'Putting it together',1,10);
CREATE TABLE placement_answers (
	id INTEGER NOT NULL, 
	test_id INTEGER NOT NULL, 
	exercise_id INTEGER NOT NULL, 
	difficulty INTEGER NOT NULL, 
	submitted JSON NOT NULL, 
	is_correct BOOLEAN NOT NULL, 
	answered_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE CASCADE, 
	FOREIGN KEY(test_id) REFERENCES placement_tests (id) ON DELETE CASCADE, 
	CONSTRAINT uq_placement_answer_test_exercise UNIQUE (test_id, exercise_id)
);
CREATE TABLE placement_tests (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	course_id INTEGER NOT NULL, 
	started_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	result_level INTEGER, 
	result_score INTEGER, 
	result_max_score INTEGER, 
	result_skill_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
	FOREIGN KEY(result_skill_id) REFERENCES skills (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE sessions (
	id VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE skills (
	id INTEGER NOT NULL, 
	unit_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	order_index INTEGER NOT NULL, 
	icon VARCHAR(48) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unit_id) REFERENCES units (id) ON DELETE CASCADE, 
	CONSTRAINT uq_skill_order_in_unit UNIQUE (unit_id, order_index)
);
INSERT INTO "skills" VALUES(1,1,'Greetings','Hello, goodbye and the times of day.',0,'waving_hand');
INSERT INTO "skills" VALUES(2,1,'Introductions','Say your name and ask how someone is.',1,'person');
INSERT INTO "skills" VALUES(3,1,'Basics','Yes, no, and asking simple questions.',2,'school');
INSERT INTO "skills" VALUES(4,2,'Food','Order a drink and name what you eat.',0,'restaurant');
INSERT INTO "skills" VALUES(5,2,'Family','Talk about the people closest to you.',1,'group');
INSERT INTO "skills" VALUES(6,2,'Animals','Pets and common animals.',2,'pets');
INSERT INTO "skills" VALUES(7,3,'Numbers','Count from one to ten.',0,'tag');
INSERT INTO "skills" VALUES(8,3,'Common verbs','Eat, drink, speak, live, have.',1,'bolt');
INSERT INTO "skills" VALUES(9,3,'Simple sentences','Put the words together.',2,'menu_book');
CREATE TABLE units (
	id INTEGER NOT NULL, 
	course_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	order_index INTEGER NOT NULL, 
	color_key VARCHAR(24) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
	CONSTRAINT uq_unit_order_in_course UNIQUE (course_id, order_index)
);
INSERT INTO "units" VALUES(1,1,'Greetings and basics','Say hello, introduce yourself, and be polite.',0,'green');
INSERT INTO "units" VALUES(2,1,'Everyday life','Food, family and animals — the words you use daily.',1,'blue');
INSERT INTO "units" VALUES(3,1,'Numbers and actions','Count, use common verbs, and build real sentences.',2,'purple');
CREATE TABLE user_achievements (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	achievement_id INTEGER NOT NULL, 
	unlocked_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(achievement_id) REFERENCES achievements (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT uq_user_achievement UNIQUE (user_id, achievement_id)
);
CREATE TABLE user_onboarding (
	user_id INTEGER NOT NULL, 
	course_id INTEGER, 
	proficiency VARCHAR(24), 
	starting_mode VARCHAR(16), 
	placement_level INTEGER, 
	placement_skill_id INTEGER, 
	started_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE SET NULL, 
	FOREIGN KEY(placement_skill_id) REFERENCES skills (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT ck_proficiency_level CHECK (proficiency IN ('BEGINNER', 'COMMON_WORDS', 'BASIC_CONVERSATION', 'VARIOUS_TOPICS', 'ADVANCED')), 
	CONSTRAINT ck_starting_mode CHECK (starting_mode IN ('SCRATCH', 'PLACEMENT'))
);
CREATE TABLE user_skill_progress (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	skill_id INTEGER NOT NULL, 
	lessons_completed INTEGER NOT NULL, 
	crowns INTEGER NOT NULL, 
	xp_earned INTEGER NOT NULL, 
	last_completed_at DATETIME, 
	placed_out_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT uq_progress_user_skill UNIQUE (user_id, skill_id)
);
INSERT INTO "user_skill_progress" VALUES(1,1,1,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(2,1,2,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(3,1,3,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(4,1,4,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(5,1,5,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(6,1,6,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(7,1,7,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(8,1,8,0,0,0,NULL,NULL);
INSERT INTO "user_skill_progress" VALUES(9,1,9,0,0,0,NULL,NULL);
CREATE TABLE user_stats (
	user_id INTEGER NOT NULL, 
	total_xp INTEGER NOT NULL, 
	gems INTEGER NOT NULL, 
	hearts INTEGER NOT NULL, 
	hearts_updated_at DATETIME NOT NULL, 
	current_streak INTEGER NOT NULL, 
	longest_streak INTEGER NOT NULL, 
	last_activity_date DATE, 
	daily_goal INTEGER NOT NULL, 
	daily_xp INTEGER NOT NULL, 
	PRIMARY KEY (user_id), 
	CONSTRAINT ck_user_stats_hearts CHECK (hearts >= 0 AND hearts <= 5), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "user_stats" VALUES(1,0,540,5,'2026-09-08 07:54:42.973643',0,0,NULL,30,0);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	display_name VARCHAR(80) NOT NULL, 
	avatar_url VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (display_name), 
	UNIQUE (email), 
	UNIQUE (username)
);
INSERT INTO "users" VALUES(1,'learner','learner@example.com','$2b$12$QotvQx7ZFKLsZ9eFCTZUXOofbE51PvoYxmcgbyqK1a7v0Wrvx.zA.','Alex Mercer','/learner-avatar.png','2026-09-08 07:54:42.969427');
CREATE INDEX ix_sessions_user_id ON sessions (user_id);
CREATE INDEX ix_units_course_id ON units (course_id);
CREATE INDEX ix_user_achievements_user_id ON user_achievements (user_id);
CREATE INDEX ix_skills_unit_id ON skills (unit_id);
CREATE INDEX ix_lessons_skill_id ON lessons (skill_id);
CREATE INDEX ix_placement_tests_user_id ON placement_tests (user_id);
CREATE INDEX ix_user_onboarding_course_id ON user_onboarding (course_id);
CREATE INDEX ix_user_skill_progress_skill_id ON user_skill_progress (skill_id);
CREATE INDEX ix_user_skill_progress_user_id ON user_skill_progress (user_id);
CREATE INDEX ix_exercises_lesson_id ON exercises (lesson_id);
CREATE INDEX ix_lesson_attempts_lesson_id ON lesson_attempts (lesson_id);
CREATE INDEX ix_lesson_attempts_user_id ON lesson_attempts (user_id);
CREATE INDEX ix_lesson_attempts_user_lesson ON lesson_attempts (user_id, lesson_id);
CREATE INDEX ix_lesson_attempt_answers_attempt_id ON lesson_attempt_answers (attempt_id);
CREATE INDEX ix_lesson_attempt_pairs_attempt_exercise ON lesson_attempt_pairs (attempt_id, exercise_id);
CREATE INDEX ix_placement_answers_test_id ON placement_answers (test_id);
COMMIT;
