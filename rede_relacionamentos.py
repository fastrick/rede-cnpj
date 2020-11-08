# -*- coding: utf-8 -*-
"""
Created on set/2020
json a partir da tabela sqlite

@author: tomita
"""

#import pymysql as mysqllib #tem que definir autocommit=True
import time, copy, json, re, string, unicodedata, collections

import pandas as pd, sqlalchemy
#import sqlite3, 
import sys, configparser
config = configparser.ConfigParser()
config.read('rede.ini')
try:
    camDbSqlite = config['rede']['caminhoDBSqlite']
except:
    #print('o arquivo sqlite não foi localizado. Veja o arquivo de configuracao rede.ini')
    sys.exit('o arquivo sqlite não foi localizado. Veja o caminho da base no arquivo de configuracao rede.ini está correto.')
try:
    caminhoDBLinks = config['rede']['caminhoDBLinks']
except:
    caminhoDBLinks = ''
try:
    logAtivo = True if config['rede']['logAtivo']=='1' else False #registra cnpjs consultados
except:
    logAtivo = False
try:
    ligacaoSocioFilial = True if config['rede']['ligacaoSocioFilial']=='1' else False #registra cnpjs consultados
except:
    ligacaoSocioFilial = True
      
dfaux = pd.read_csv(r"tabelas/tabela-de-qualificacao-do-socio-representante.csv", sep=';')
dicQualificacao_socio = pd.Series(dfaux.descricao.values,index=dfaux.codigo).to_dict()
dfaux = pd.read_csv(r"tabelas/DominiosMotivoSituaoCadastral.csv", sep=';', encoding='latin1')
dicMotivoSituacao = pd.Series(dfaux['Descrição'].values, index=dfaux['Código']).to_dict()
dfaux = pd.read_excel(r"tabelas/cnae.xlsx", sheet_name='codigo-grupo-classe-descr')
dicCnae = pd.Series(dfaux['descricao'].values, index=dfaux['codigo']).to_dict()
dicSituacaoCadastral = {'01':'Nula', '02':'Ativa', '03':'Suspensa', '04':'Inapta', '08':'Baixada'}
dicPorteEmpresa = {'00':'Não informado', '01':'Micro empresa', '03':'Empresa de pequeno porte', '05':'Demais (Médio ou Grande porte)'}
dfaux = pd.read_csv(r"tabelas/natureza_juridica.csv", sep=';', encoding='utf8', dtype=str)
dicNaturezaJuridica = pd.Series(dfaux['natureza_juridica'].values, index=dfaux['codigo']).to_dict()

dfaux=None

def buscaPorNome(nome): #nome tem que ser completo. Com Teste, pega item randomico
    #remove acentos
    con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    nome = ''.join(x for x in unicodedata.normalize('NFKD', nome) if x in string.printable).upper()
    cjs, cps = set(), set()
    if (' ' not in nome) and (nome not in ('TESTE',)): #só busca nome
        return cjs, cps
    if nome=='TESTE':
        query = 'select cnpj_cpf_socio, nome_socio from socios where rowid > (abs(random()) % (select (select max(rowid) from socios)+1)) LIMIT 1;'
    else:
        query = f'''
                SELECT cnpj_cpf_socio, nome_socio
                FROM socios 
                where nome_socio=\"{nome}\"
            '''
    for r in con.execute(query):
        if len(r.cnpj_cpf_socio)==14:
            cjs.add(r.cnpj_cpf_socio)
        elif len(r.cnpj_cpf_socio)==11:
            cps.add((r.cnpj_cpf_socio, r.nome_socio))
    if nome=='TESTE':
        print('##TESTE', cjs, cps)
    # pra fazer busca por razao_social, a coluna deve estar indexada
    query = f'''
                SELECT cnpj
                FROM empresas 
                where razao_social=\"{nome}\"
            '''        
    for r in con.execute(query):
        cjs.add(r.cnpj)     
    con = None
    return cjs, cps
#.def buscaPorNome(

def separaEntrada(cpfcnpjIn='', listaCpfCnpjs=None):
    cnpjs = set()
    cpfnomes = set()
    if cpfcnpjIn:
        lista = cpfcnpjIn.split(';')
        lista = [i.strip() for i in lista]
    else:
        lista = listaCpfCnpjs
    for i in lista:
        if i.startswith('PJ_'):
            cnpjs.add(i[3:])
        elif i.startswith('PF_'):
            cpfcnpjnome = i[3:]
            cpf = cpfcnpjnome[:11]
            nome = cpfcnpjnome[12:]
            cpfnomes.add((cpf,nome))  
        else:
            soDigitos = ''.join(re.findall('\d', str(i)))
            if len(soDigitos)==14:
                cnpjs.add(soDigitos)
            elif len(soDigitos)==11:
                pass #fazer verificação por CPF??
            elif not soDigitos:
                cnpjsaux, cpfnomesaux = buscaPorNome(i)
                cnpjs.update(cnpjsaux)
                cpfnomes.update(cpfnomesaux)  
    return cnpjs, cpfnomes
#.def separaEntrada

def ajustaLabelIcone(nosaux):
    nos = []
    for no in nosaux:
        prefixo =no['id'].split('_')[0]
        no['tipo'] = prefixo
        if prefixo=='PF':    
            no['label'] =  no['id'].replace('-','\n',1)
        elif prefixo=='PJ':
            no['label'] =  no['id'] + '\n' + no.get('descricao','')
        else:
            no['label'] = no['id']
        if prefixo=='PF':
            no['sexo'] = provavelSexo(no.get('id',''))
            if no['sexo']==1:
                imagem = 'icone-grafo-masculino.png'
            elif no['sexo']==2:
                imagem = 'icone-grafo-feminino.png'
            else:
                imagem = 'icone-grafo-desconhecido.png'
        elif prefixo=='END':
            imagem = 'icone-grafo-endereco.png'
        else:
            codnat = no['cod_nat_juridica']
            if codnat.startswith('1'):
                imagem = 'icone-grafo-empresa-publica.png'
            elif codnat.startswith('2'):
                imagem = 'icone-grafo-empresa.png'
            elif codnat.startswith('3'):
                imagem = 'icone-grafo-empresa-fundacao.png'
            elif codnat.startswith('4'):
                imagem = 'icone-grafo-empresa-individual.png'
            elif codnat.startswith('5'):
                imagem = 'icone-grafo-empresa-estrangeira.png'                
            else:
                imagem = 'icone-grafo-empresa.png'
        no['imagem'] = '/rede/static/imagem/' + imagem
        nos.append(copy.deepcopy(no))
    return nos 
#.def ajustaLabelIcone

def jsonRede(cpfcnpjIn, camada=1 ):    
    if cpfcnpjIn:
        return camadasRede(cpfcnpjIn = cpfcnpjIn, camada=camada, bjson=True)
    else:
        return {'no': [], 'ligacao':[]} 
#.def jsonRede

dtype_tmp_cnpjs={'cnpj':sqlalchemy.types.VARCHAR,
                       'grupo':sqlalchemy.types.VARCHAR,
                       'camada':sqlalchemy.types.INTEGER }
dtype_tmp_cpfnomes={'cpf':sqlalchemy.types.VARCHAR,
                       'nome':sqlalchemy.types.VARCHAR,
                       'grupo':sqlalchemy.types.VARCHAR,
                       'camada':sqlalchemy.types.INTEGER }

def criaTabelasTmpParaCamadas(con, cpfcnpjIn='', grupo='', listaCpfCnpjs=None, tabelaIds=False):
    #con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    con.execute('DROP TABLE IF EXISTS tmp_cnpjs;')
    con.execute('DROP TABLE IF EXISTS tmp_cpfnomes;')
    con.execute('''
        CREATE TEMP TABLE tmp_cnpjs (
    	cnpj VARCHAR, 
    	grupo VARCHAR, 
    	camada INTEGER
        )''')
    con.execute('''
        CREATE TEMP TABLE tmp_cpfnomes (
    	cpf VARCHAR, 
    	nome VARCHAR, 
    	grupo VARCHAR, 
    	camada INTEGER
        )''')
    if cpfcnpjIn:
        cnpjs, cpfnomes = separaEntrada(cpfcnpjIn=cpfcnpjIn)
    else:
        cnpjs, cpfnomes = separaEntrada(listaCpfCnpjs=listaCpfCnpjs)
    camadasIds = {}
    ids = set()
    if tabelaIds:
        ids = set(['PJ_'+c for c in cnpjs])
        ids.union(set(['PF_'+cpf+'-'+nome for cpf,nome in cpfnomes]))
        con.execute('DROP TABLE IF EXISTS tmp_ids;')
        con.execute('''
            CREATE TEMP TABLE tmp_ids (
        	identificador VARCHAR,
            grupo VARCHAR
            camada INTEGER
            )''')
        dftmptable = pd.DataFrame({'identificador' : list(ids)})
        dftmptable['camada'] = 0
        dftmptable['grupo'] = grupo
        dftmptable.to_sql('tmp_ids', con=con, if_exists='replace', index=False, dtype=sqlalchemy.types.VARCHAR)
        camadasIds = {i:0 for i in ids}
    for cnpj in cnpjs:
        camadasIds[cnpj]=0
    for cpf,nome in cpfnomes:
        camadasIds[(cpf, nome)] = 0;
    dftmptable = pd.DataFrame({'cnpj' : list(cnpjs)})
    dftmptable['grupo'] = grupo
    dftmptable['camada'] = 0
    dftmptable.to_sql('tmp_cnpjs', con=con, if_exists='append', index=False, dtype=dtype_tmp_cnpjs)

    dftmptable = pd.DataFrame(list(cpfnomes), columns=['cpf', 'nome'])
    dftmptable['grupo'] = grupo
    dftmptable['camada'] = 0
    dftmptable.to_sql('tmp_cpfnomes', con=con, if_exists='append', index=False, dtype=dtype_tmp_cpfnomes)    
    return camadasIds, cnpjs, cpfnomes, ids
#.def criaTabelasTmpParaCamadas

def camadasRede(cpfcnpjIn='', camada=1, grupo='', bjson=True, listaCpfCnpjs=None  ):    
    #se cpfcnpjIn=='', usa dados das tabelas tmp_cnpjs e tmp_cpfnomes, não haverá camada=0
    #se fromTmpTable=False, espera que cpfcnpjIn='cpf-nome;cnpj;nome...'
    #se fromTmpTable=True, ignora cpfcnpjIn e pega dados a partir de tmp_cnpjs e tmp_cpfnomes
    #print('INICIANDO-------------------------')
    print(f'camadasRede ({camada})-{cpfcnpjIn}-inicio: ' + time.ctime() + ' ', end='')
    mensagem = {'lateral':'', 'popup':'', 'confirmar':''}
    #con=sqlite3.connect(camDbSqlite)
    con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    grupo = str(grupo)
    nosaux = []
    nosids = set()
    ligacoes = []
    setOrigDest = set()
    camadasIds, cnpjs, cpfnomes, setOrigDest  = criaTabelasTmpParaCamadas(con, cpfcnpjIn=cpfcnpjIn, grupo=grupo, listaCpfCnpjs=listaCpfCnpjs)
    # if cpfcnpjIn:
    #     camadasIds = criaTabelasTmpParaCamadas(con, cpfcnpjIn=cpfcnpjIn, grupo=grupo, listaCpfCnpjs=listaCpfCnpjs)
    # else:
    #     camadasIds = {}
 
    #cnpjs=set() #precisa adicionar os cnpjs que não tem sócios
    #cpfnomes = set()
    dicRazaoSocial = {} #excepcional, se um cnpj que é sócio na tabela de socios não tem cadastro na tabela empresas
    for cam in range(camada):       
        query = ''' SELECT * From (
                    SELECT t.cnpj, cnpj_cpf_socio, nome_socio, tipo_socio, cod_qualificacao
                    FROM socios t
                    INNER JOIN tmp_cnpjs tl
                    ON  tl.cnpj = t.cnpj
                    UNION
                    SELECT t.cnpj, cnpj_cpf_socio, nome_socio, tipo_socio, cod_qualificacao
                    FROM socios t
                    INNER JOIN tmp_cnpjs tl
                    ON tl.cnpj = t.cnpj_cpf_socio
                    UNION
                    SELECT t.cnpj, cnpj_cpf_socio, nome_socio, tipo_socio, cod_qualificacao
                    FROM socios t
                    INNER JOIN tmp_cpfnomes tn ON tn.nome= t.nome_socio AND tn.cpf=t.cnpj_cpf_socio
                    ) ORDER by cnpj, cnpj_cpf_socio, nome_socio; '''

        #no sqlite, o order by é feito após o UNION.
        ligacoes = [] #tem que reiniciar a cada loop
        orig_destAnt = ()
        for k in con.execute(query):
            cnpj = k['cnpj']
            #print('cnpj',cnpj)
            if bjson and not ligacaoSocioFilial: #not bjson
                #print('cnpj1', cnpj)
                if cnpj[8:12]!='0001': #trocar por verificação de matriz/filial
                    if camadasIds.get(cnpj,-1) !=0:
                        continue
            cnpjs.add(cnpj)
            if cnpj not in camadasIds:
                camadasIds[cnpj] = cam+1
            cnpj_cpf_socio = k['cnpj_cpf_socio']
            if len(cnpj_cpf_socio)==14:
                cnpj = cnpj_cpf_socio
                if bjson and not ligacaoSocioFilial:
                    if cnpj_cpf_socio[8:12]!='0001': #trocar por verificação de matriz/filial
                        if camadasIds.get(cnpj,-1) !=0: #se filial não for origem, não inclue
                            continue
                dicRazaoSocial[cnpj] = k['nome_socio']
                destino = 'PJ_'+ cnpj
                cnpjs.add(cnpj)
                if cnpj not in camadasIds:
                    camadasIds[cnpj] = cam+1
            else:
                destino = 'PF_'+cnpj_cpf_socio+'-'+k['nome_socio']
                cpfnome = (cnpj_cpf_socio, k['nome_socio'])
                if cpfnome not in camadasIds:
                    camadasIds[cpfnome] = cam+1
                cpfnomes.add(cpfnome)
                if cam+1==camada and bjson: #só pega dados na última camada
                    if destino not in nosids: #verificar repetição??
                        no = {'id': destino, 'descricao':k['nome_socio'], 
                              'camada': camadasIds[cpfnome], 
                              'situacao_ativa': True, 
                              #'empresa_situacao': 0, 'empresa_matriz': 1, 'empresa_cod_natureza': 0, 
                              'logradouro':'',
                              'municipio': '', 'uf': ''} #, 'm1': 0, 'm2': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0, 'm7': 0, 'm8': 0, 'm9': 0, 'm10': 0, 'm11': 0}     
                        nosids.add(destino)
                        nosaux.append(copy.deepcopy(no)) 
            #neste caso, não deve haver ligação repetida, mas é necessário colocar uma verificação se for ligações generalizadas
            if orig_destAnt == ('PJ_'+k['cnpj'], destino):
                print('XXXXXXXXXXXXXX repetiu ligacao', orig_destAnt)
            orig_destAnt = ('PJ_'+k['cnpj'], destino)
            if cam+1==camada and bjson: #só pega dados na última camada
                ligacao = {"origem":'PJ_'+k['cnpj'], "destino":destino, 
                           "cor": "silver", #"cor":"gray", 
                           "camada":cam+1, "tipoDescricao":'sócio',"label":dicQualificacao_socio.get(int(k['cod_qualificacao']),'')}
                ligacoes.append(copy.deepcopy(ligacao))
                setOrigDest.add('PJ_'+k['cnpj'])
                setOrigDest.add(destino)
        #.for k in con.execute(query):
        dftmptable = pd.DataFrame({'cnpj' : list(cnpjs)})
        dftmptable['grupo'] = grupo
        dftmptable['camada'] = dftmptable['cnpj'].apply(lambda x: camadasIds[x])
        #dftmptable['camada'] = dftmptable['cnpj'].map(camadasIds)
        con.execute('DELETE from tmp_cnpjs;')
        dftmptable.to_sql('tmp_cnpjs', con=con, if_exists='append', index=False, dtype=dtype_tmp_cnpjs)
        dftmptable = pd.DataFrame(list(cpfnomes), columns=['cpf', 'nome'])
        dftmptable['grupo'] = grupo
        dftmptable['camada'] = -1
        for r in dftmptable.itertuples():
            dftmptable.at[r.Index, 'camada'] = camadasIds[(r.cpf,r.nome)]
        #dftmptable['camada'] = dftmptable.apply(lambda r: camadasIds[(r['cpf'], r['nome'])])
        con.execute('DELETE from tmp_cpfnomes;')
        dftmptable.to_sql('tmp_cpfnomes', con=con, if_exists='append', index=False, dtype=dtype_tmp_cpfnomes)    
    

    if logAtivo or not bjson:
        conlog = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
        conlog.execute('create table if not exists log_cnpjs (cnpj text, grupo text, camada text)')
        conlog.execute('''insert into log_cnpjs 
            select * from tmp_cnpjs; ''')
        conlog.execute('create table if not exists log_cpfnomes (cpf text, nome text, grupo text, camada text);')
        conlog.execute('''insert into log_cpfnomes 
            select cpf, nome, grupo, cast(camada as int) from tmp_cpfnomes; ''')
        conlog = None
    if not bjson:
        print('camadasRede-fim: ' + time.ctime())
        return len(camadasIds)
    nos = dadosDosNos(con, cnpjs, nosaux, dicRazaoSocial, camadasIds)
    textoJson={'no': nos, 'ligacao':ligacoes, 'mensagem':mensagem} 
    con = None
    #print(' fim: ' + time.ctime())
    print(' fim: ' + ' '.join(str(time.ctime()).split()[3:]))
    return textoJson
#.def camadasRede

def dadosDosNos(con, cnpjs, nosaux, dicRazaoSocial, camadasIds):
    dftmptable = pd.DataFrame({'cnpj' : list(cnpjs)})
    dftmptable.to_sql('tmp_cnpjs', con=con, if_exists='replace', index=False, dtype=dtype_tmp_cnpjs)
    query = '''
                SELECT t.cnpj, razao_social, situacao, matriz_filial,
                tipo_logradouro, logradouro, numero, complemento, bairro,
                municipio, uf,  cod_nat_juridica
                FROM empresas t
                INNER JOIN tmp_cnpjs tp on tp.cnpj=t.cnpj
            ''' #pode haver empresas fora da base de teste
    setCNPJsRecuperados = set()
    for k in con.execute(query):
        listalogradouro = [j.strip() for j in [k['logradouro'].strip(), k['numero'], k['complemento'].strip(';'), k['bairro']] if j.strip()]
        logradouro = ', '.join(listalogradouro)
        no = {'id': 'PJ_'+k['cnpj'], 'descricao': k['razao_social'], 
              'camada': camadasIds[k['cnpj']], 'tipo':0, 'situacao_ativa': k['situacao']=='02',
              'logradouro': f'''{k['tipo_logradouro']} {logradouro}''',
              'municipio': k['municipio'], 'uf': k['uf'], 'cod_nat_juridica':k['cod_nat_juridica']
              }
        nosaux.append(copy.deepcopy(no))
        setCNPJsRecuperados.add(k['cnpj'])
    #trata caso excepcional com base de teste, cnpj que é sócio não tem registro na tabela empresas
    diffCnpj = cnpjs.difference(setCNPJsRecuperados)
    for cnpj in diffCnpj:
        no = {'id': 'PJ_'+cnpj, 'descricao': dicRazaoSocial.get(cnpj, 'NÃO FOI LOCALIZADO NA BASE'), 
              'camada': camadasIds[cnpj], 'tipo':0, 'situacao_ativa': True,
              'logradouro': '',
              'municipio': '', 'uf': '',  'cod_nat_juridica':''
              }
        nosaux.append(copy.deepcopy(no))
    #ajusta nos, colocando label
    nosaux=ajustaLabelIcone(nosaux)
    nos = nosaux #nosaux[::-1] #inverte, assim os nos de camada menor serao inseridas depois, ficando na frente
    nos.sort(key=lambda n: n['camada'], reverse=True) #inverte ordem, porque os últimos icones vão aparecer na frente. Talvez na prática não seja útil.
    return nos
#.def dadosDosNos

def camadaLink(cpfcnpjIn='', camada=1, numeroItens=15, valorMinimo=0, valorMaximo=0, grupo='', bjson=True, listaCpfCnpjs=None  ):    
    #se cpfcnpjIn=='', usa dados das tabelas tmp_cnpjs e tmp_cpfnomes, não haverá camada=0
    #se fromTmpTable=False, espera que cpfcnpjIn='cpf-nome;cnpj;nome...'
    #se fromTmpTable=True, ignora cpfcnpjIn e pega dados a partir de tmp_cnpjs e tmp_cpfnomes
    #print('INICIANDO-------------------------')
    print(f'camadasRede ({camada})-{cpfcnpjIn}-inicio: ' + time.ctime() + ' ', end='')
    mensagem = {'lateral':'', 'popup':'', 'confirmar':''}
    if not caminhoDBLinks:
        mensagem['popup'] = 'Não há tabela de links configurada.'
        return {'no': [], 'ligacao':[], 'mensagem': mensagem} 
    #con=sqlite3.connect(camDbSqlite)
    #caminhoDBLinks = 'tce_despesas.db'
    con = sqlalchemy.create_engine(f"sqlite:///{caminhoDBLinks}", execution_options={"sqlite_raw_colnames": True})
    grupo = str(grupo)
    nosaux = []
    #nosids = set()
    ligacoes = []
    setLigacoes = set()
    camadasIds, cnpjs, cpfnomes, nosids = criaTabelasTmpParaCamadas(con, cpfcnpjIn=cpfcnpjIn, grupo=grupo, listaCpfCnpjs=listaCpfCnpjs, tabelaIds=True)

    dicRazaoSocial = {} #excepcional, se um cnpj que é sócio na tabela de socios não tem cadastro na tabela empresas
    limite = numeroItens #15
    #passo = numeroItens*2 #15
    #cnt1 = collections.Counter() #contadores de links para o id1 e id2
    #cnt2 = collections.Counter()    
    cntlink = collections.Counter()
    for cam in range(camada):       
        query = ''' SELECT * From (
                    SELECT t.id1, t.id2, t.descricao, t.valor
                    FROM links t
                    INNER JOIN tmp_ids tl
                    ON  tl.identificador = t.id1
                    UNION
                    SELECT t.id1, t.id2, t.descricao, t.valor
                    FROM links t
                    INNER JOIN tmp_ids tl
                    ON  tl.identificador = t.id2
                     ) ORDER by valor DESC
                    '''
        #no sqlite, o order by é feito após o UNION.
        #ligacoes = [] #tem que reiniciar a cada loop
        orig_destAnt = ()

        #tem que mudar o método, teria que fazer uma query para cada entrada
        for k in con.execute(query + ' LIMIT ' + str(limite)):
            if not(k['id1']) or not(k['id2']):
                print('####link invalido!!!', k['id1'], k['id2'], k['descricao'], k['valor'])
                continue #caso a tabela esteja inconsistente
            #limita a quantidade de ligacoes por item
            if cntlink[k['id1']]>numeroItens or cntlink[k['id2']]>numeroItens:
                continue
            if valorMinimo:
                if k['valor']<valorMinimo:
                     continue
            if valorMaximo:
                if valorMaximo < k['valor']:
                    continue
            cntlink[k['id1']] += 1
            cntlink[k['id2']] += 1
            
            nosids.add(k['id1'])
            nosids.add(k['id2'])
            if k['id1'] not in camadasIds:
                camadasIds[k['id1']] = cam+1            
            if k['id2'] not in camadasIds:
                camadasIds[k['id2']] = cam+1
            #neste caso, não deve haver ligação repetida, mas é necessário colocar uma verificação se for ligações generalizadas
            # if orig_destAnt == ('PJ_'+k['cnpj'], destino):
            #     print('XXXXXXXXXXXXXX repetiu ligacao', orig_destAnt)
            # orig_destAnt = ('PJ_'+k['cnpj'], destino)
            if (k['id1'], k['id2']) not in setLigacoes: #cam+1==camada and bjson: #só pega dados na última camada
                ligacao = {"origem":k['id1'], "destino":k['id2'], 
                           "cor": "gold", #"cor":"gray", 
                           "camada":cam+1, "tipoDescricao":'link',"label":k['descricao'] + ':' + ajustaValor(k['valor'])}
                ligacoes.append(copy.deepcopy(ligacao))
                setLigacoes.add((k['id1'], k['id2']))
            else:
                print('####ligacao repetida. A implementar')
        #.for k in con.execute(query):
        listaProximaCamada = [item for item in nosids if camadasIds[item]>cam]
        dftmptable = pd.DataFrame({'identificador' : listaProximaCamada})
        dftmptable['grupo'] = grupo
        dftmptable['camada'] = dftmptable['identificador'].apply(lambda x: camadasIds[x])
        #dftmptable['camada'] = dftmptable['cnpj'].map(camadasIds)
        con.execute('DELETE from tmp_ids;')
        dftmptable.to_sql('tmp_ids', con=con, if_exists='replace', index=False, dtype=sqlalchemy.types.VARCHAR)
        limite = limite * numeroItens * 2

    # if logAtivo or not bjson:
    #     conlog = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    #     conlog.execute('create table if not exists log_cnpjs (cnpj text, grupo text, camada text)')
    #     conlog.execute('''insert into log_cnpjs 
    #         select * from tmp_cnpjs; ''')
    #     conlog.execute('create table if not exists log_cpfnomes (cpf text, nome text, grupo text, camada text);')
    #     conlog.execute('''insert into log_cpfnomes 
    #         select cpf, nome, grupo, cast(camada as int) from tmp_cpfnomes; ''')
    #     conlog = None
    # if not bjson:
    #     print('camadasRede-fim: ' + time.ctime())
    #     return len(camadasIds)
    #cnpjs = set([c[3:] for c in setOrigDest if c.startswith('PJ_')])
    #print('nosids', nosids)
    for c in nosids:
        if c.startswith('PJ_'):
            cnpjs.add(c[3:])
    for c in cnpjs:
        camadasIds[c] = camadasIds['PJ_'+c]
    conCNPJ = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    nos = dadosDosNos(conCNPJ, cnpjs, nosaux, dicRazaoSocial, camadasIds)
    textoJson={'no': nos, 'ligacao':ligacoes, 'mensagem':mensagem} 
    con = None
    conCNPJ = None
    #print(' fim: ' + time.ctime())
    print(' fim: ' + ' '.join(str(time.ctime()).split()[3:]))
    return textoJson
#.def camadaLink

def apagaLog():
    con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    con.execute('DROP TABLE IF EXISTS log_cnpjs;')
    con.execute('DROP TABLE IF EXISTS log_cpfnomes;')
    con = None
                
def jsonDados(cpfcnpjIn):    
    #print('INICIANDO-------------------------')
    #dados de cnpj para popup de Dados
    print('jsonDados-inicio: ' + time.ctime())
    con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    cnpjs, cpfnomes = separaEntrada(cpfcnpjIn)    
    dftmptable = pd.DataFrame({'cnpj' : list(cnpjs)})
    dftmptable.to_sql('tmp_cnpjs1', con=con, if_exists='replace', index=False, dtype=sqlalchemy.types.VARCHAR)
    query = '''
                SELECT *
                FROM empresas t
                INNER JOIN tmp_cnpjs1 tp on tp.cnpj=t.cnpj
            '''
    dados = ""
    for k in con.execute(query):
        d = dict(k)  
        capital = d['capital_social']/100
        capital = f"{capital:,.2f}".replace(',','@').replace('.',',').replace('@','.')
        listalogradouro = [k.strip() for k in [d['logradouro'].strip(), d['numero'], d['complemento'].strip(';'), d['bairro']] if k.strip()]
        logradouro = ', '.join(listalogradouro)
        d['cnpj'] = f"{d['cnpj']} - {'Matriz' if d['matriz_filial']=='1' else 'Filial'}"
        d['data_inicio_ativ'] = ajustaData(d['data_inicio_ativ'])
        d['situacao'] = f"{d['situacao']} - {dicSituacaoCadastral.get(d['situacao'],'')}"
        d['data_situacao'] = ajustaData(d['data_situacao']) 
        d['motivo_situacao'] = f"{d['motivo_situacao']}-{dicMotivoSituacao.get(int(d['motivo_situacao']),'')}"
        d['cod_nat_juridica'] = f"{d['cod_nat_juridica']}-{dicNaturezaJuridica.get(d['cod_nat_juridica'],'')}"
        d['cnae_fiscal'] = f"{d['cnae_fiscal']}-{dicCnae.get(int(d['cnae_fiscal']),'')}"
        d['porte'] = f"{d['porte']}-{dicPorteEmpresa.get(d['porte'],'')}"
        d['endereco'] = f"{d['tipo_logradouro']} {logradouro}"
        d['capital_social'] = capital 
        break #só pega primeiro
    con = None
    print('jsonDados-fim: ' + time.ctime())   
    return d
#.def jsonDados


def ajustaValor(valor):
    if valor>=10000000.0:
        v = '{:.0f}'.format(valor/1000000).replace('.',',') + ' MI'
    elif valor>=1000000.0:
        v = '{:.1f}'.format(valor/1000000).replace('.',',') + ' MI'
    elif valor>=10000.0:
        v = '{:.0f}'.format(valor/1000).replace('.',',') + ' mil'
    elif valor>=1000.0:
        v = '{:.1f}'.format(valor/1000).replace('.',',') + ' mil'
    else:
        v = '{:.2f}'.format(valor).replace('.',',')
    return v
        
def ajustaData(d): #aaaammdd
    return d[-2:]+'/' + d[4:6] + '/' + d[:4]

def dadosParaExportar(listaCpfCnpjs):    
    print('dadosParaExportar-inicio: ' + time.ctime())
    con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    criaTabelasTmpParaCamadas(con, listaCpfCnpjs=listaCpfCnpjs, grupo='')
    querysocios = '''
                SELECT * from
				(SELECT t.cnpj, te.razao_social, t.cnpj_cpf_socio, t.nome_socio, t.tipo_socio, t.cod_qualificacao
                FROM socios t
                INNER JOIN tmp_cnpjs tl ON  tl.cnpj = t.cnpj
                LEFT JOIN empresas te on te.cnpj=t.cnpj
                UNION
                SELECT t.cnpj, te.razao_social, t.cnpj_cpf_socio, t.nome_socio, t.tipo_socio, t.cod_qualificacao
                FROM socios t
                INNER JOIN tmp_cnpjs tl ON tl.cnpj = t.cnpj_cpf_socio
                LEFT JOIN empresas te on te.cnpj=t.cnpj
                UNION
                SELECT t.cnpj, te.razao_social, t.cnpj_cpf_socio, t.nome_socio, t.tipo_socio, t.cod_qualificacao
                FROM socios t
                INNER JOIN tmp_cpfnomes tn ON tn.nome= t.nome_socio AND tn.cpf=t.cnpj_cpf_socio
                LEFT JOIN empresas te on te.cnpj=t.cnpj)
                ORDER BY nome_socio
            '''

    queryempresas = '''
                SELECT *
                FROM empresas t
                INNER JOIN tmp_cnpjs tp on tp.cnpj=t.cnpj
            '''
    from io import BytesIO
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    #workbook = writer.book
    dfin = pd.DataFrame(listaCpfCnpjs, columns=['cpfcnpj'])
    dfin.to_excel(writer, startrow = 0, merge_cells = False, sheet_name = "lista", index=False)
    dfe=pd.read_sql_query(queryempresas, con)
    dfe['capital_social'] = dfe['capital_social'].apply(lambda capital: f"{capital/100:,.2f}".replace(',','@').replace('.',',').replace('@','.'))
    
    dfe['matriz_filial'] = dfe['matriz_filial'].apply(lambda x:'Matriz' if x=='1' else 'Filial')
    dfe['data_inicio_ativ'] = dfe['data_inicio_ativ'].apply(ajustaData)
    dfe['situacao'] = dfe['situacao'].apply(lambda x: dicSituacaoCadastral.get(x,''))
                                            
    dfe['data_situacao'] =  dfe['data_situacao'].apply(ajustaData)
    dfe['motivo_situacao'] = dfe['motivo_situacao'].apply(lambda x: x + '-' + dicMotivoSituacao.get(int(x),''))
    dfe['cod_nat_juridica'] = dfe['cod_nat_juridica'].apply(lambda x: x + '-' + dicNaturezaJuridica.get(x,''))
    dfe['cnae_fiscal'] = dfe['cnae_fiscal'].apply(lambda x: x+'-'+dicCnae.get(int(x),''))
    
    dfe['porte'] = dfe['porte'].apply(lambda x: x+'-'+dicPorteEmpresa.get(x,''))
    
    dfe.to_excel(writer, startrow = 0, merge_cells = False, sheet_name = "Empresas", index=False)

    dfs=pd.read_sql_query(querysocios, con)
    dfs['cod_qualificacao'] =  dfs['cod_qualificacao'].apply(lambda x:x + '-' + dicQualificacao_socio.get(int(x),''))
    dfs.to_excel(writer, startrow = 0, merge_cells = False, sheet_name = "Socios", index=False)

    writer.close()
    output.seek(0)
    con = None
    return output

    #https://github.com/jmcarpenter2/swifter
    #dfe['data_inicio_ativ'] = dfe['data_inicio_ativ'].swifter.apply(lambda x: )
#.def dadosParaExportar

def provavelSexo(nome):
    carac = nome.split(' ')[0][-1].upper()
    if carac=='O':
        sexo = 1
    elif carac=='A':
        sexo = 2
    else:
        sexo = 0
    return sexo

def numeroDeEmpresasNaBase(): #nome tem que ser completo. Com Teste, pega item randomico
    #remove acentos
    con = sqlalchemy.create_engine(f"sqlite:///{camDbSqlite}", execution_options={"sqlite_raw_colnames": True})
    r = con.execute('select count(*) as contagem from empresas;')
    return r.fetchone()[0]
