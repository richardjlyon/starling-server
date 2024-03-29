CREATE MIGRATION m1wirdluqcbzb5dbxgyxvtzwkd6vwjitee23cacrz73djibwq66huq
    ONTO initial
{
  CREATE TYPE default::Account {
      CREATE PROPERTY created_at -> std::datetime;
      CREATE REQUIRED PROPERTY currency -> std::str;
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY uuid -> std::uuid {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::Bank {
      CREATE REQUIRED PROPERTY name -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::Account {
      CREATE REQUIRED LINK bank -> default::Bank {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
  ALTER TYPE default::Bank {
      CREATE MULTI LINK accounts := (.<bank[IS default::Account]);
  };
  CREATE TYPE default::Transaction {
      CREATE REQUIRED LINK account -> default::Account {
          ON TARGET DELETE  DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY amount -> std::float32;
      CREATE PROPERTY reference -> std::str;
      CREATE REQUIRED PROPERTY time -> std::datetime;
      CREATE REQUIRED PROPERTY uuid -> std::uuid {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::Account {
      CREATE MULTI LINK transactions := (.<account[IS default::Transaction]);
  };
  CREATE TYPE default::Category {
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY uuid -> std::uuid {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::CategoryGroup {
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY uuid -> std::uuid {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::Category {
      CREATE REQUIRED LINK category_group -> default::CategoryGroup {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
  ALTER TYPE default::CategoryGroup {
      CREATE MULTI LINK categories := (.<category_group[IS default::Category]);
  };
  ALTER TYPE default::Transaction {
      CREATE LINK category -> default::Category;
  };
  ALTER TYPE default::Category {
      CREATE MULTI LINK transactions := (.<category[IS default::Transaction]);
  };
  CREATE TYPE default::CategoryMap {
      CREATE LINK category -> default::Category;
      CREATE PROPERTY displayname -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::Counterparty {
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY uuid -> std::uuid {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::Transaction {
      CREATE REQUIRED LINK counterparty -> default::Counterparty {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
  ALTER TYPE default::Counterparty {
      CREATE MULTI LINK transactions := (.<counterparty[IS default::Transaction]);
  };
  CREATE TYPE default::DisplaynameMap {
      CREATE PROPERTY displayname -> std::str;
      CREATE PROPERTY name -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
};
