-- This update makes all the JSONB columns (if needed) arrays

-- model: Guild
alter table guild add column new_allowed_channels bigint[] default array[]::bigint[];
alter table guild add column new_allowed_roles bigint[] default array[]::bigint[];
alter table guild add column new_allowed_users bigint[] default array[]::bigint[];
alter table guild add column new_bypassed_users bigint[] default array[]::bigint[];
alter table guild add column new_bypassed_roles bigint[] default array[]::bigint[];

update guild set new_allowed_channels = (
    case
        when guild.allowed_channels is not null and guild.allowed_channels::jsonb <> 'null'::jsonb
        then array(
            select cast(value as bigint)
            from jsonb_array_elements_text(guild.allowed_channels::jsonb) as value
        )
        else array[]::bigint[]
    end
);

update guild set new_allowed_roles = (
    case
        when guild.allowed_roles is not null and guild.allowed_roles::jsonb <> 'null'::jsonb
        then array(
            select cast(value as bigint)
            from jsonb_array_elements_text(guild.allowed_roles::jsonb) as value
        )
        else array[]::bigint[]
    end
);

update guild set new_allowed_users = (
    case
        when guild.allowed_users is not null and guild.allowed_users::jsonb <> 'null'::jsonb
        then array(
            select cast(value as bigint)
            from jsonb_array_elements_text(guild.allowed_users::jsonb) as value
        )
        else array[]::bigint[]
    end
);

update guild set new_bypassed_users = (
    case
        when guild.bypassed_users is not null and guild.bypassed_users::jsonb <> 'null'::jsonb
        then array(
            select cast(value as bigint)
            from jsonb_array_elements_text(guild.bypassed_users::jsonb) as value
        )
        else array[]::bigint[]
    end
);

update guild set new_bypassed_roles = (
    case
        when guild.bypassed_roles is not null and guild.bypassed_roles::jsonb <> 'null'::jsonb
        then array(
            select cast(value as bigint)
            from jsonb_array_elements_text(guild.bypassed_roles::jsonb) as value
        )
        else array[]::bigint[]
    end
);


alter table guild drop column allowed_channels;
alter table guild drop column allowed_roles;
alter table guild drop column allowed_users;
alter table guild drop column bypassed_users;
alter table guild drop column bypassed_roles;

alter table guild rename column new_allowed_channels to allowed_channels;
alter table guild rename column new_allowed_roles to allowed_roles:
alter table guild rename column new_allowed_users to allowed_users;
alter table guild rename column new_bypassed_users to bypassed_users;
alter table guild rename column new_bypassed_roles to bypassed_roles;


-- model: VouchsConfig
alter table vouchsconfig add column new_whitelisted_channels bigint[] default array[]::bigint[];

update vouchsconfig set new_whitelisted_channels = (
    case
        when vouchsconfig.whitelisted_channels is not null and vouchsconfig.whitelisted_channels::jsonb <> 'null'::jsonb
        then array(
            select cast(value as bigint)
            from jsonb_array_elements_text(vouchsconfig.whitelisted_channels::jsonb) as value
        )
        else array[]::bigint[]
    end
);

alter table vouchsconfig drop column whitelisted_channels;

alter table vouchsconfig rename column new_whitelisted_channels to whitelisted_channels;


-- model: VouchGuildUser
alter table vouchguilduser add column new_recent char[] default array[]::char[];

update vouchguilduser set new_recent = (
    case
        when vouchguilduser.recent is not null and vouchguilduser.recent::jsonb <> 'null'::jsonb
        then array(
            select cast(value as char)
            from jsonb_array_elements_text(vouchguilduser.recent::jsonb) as value
        )
    end
);

alter table vouchguilduser drop column recent;

alter table vouchguilduser rename column new_recent to recent;


-- model: GuildApplication
alter table guildapplication add column new_questions jsonb[] default array[]::jsonb[];

update guildapplication set new_questions = (
    case
        when guildapplication.questions is not null and guildapplication.questions::jsonb <> 'null'::jsonb
        then array(
            select cast(value as jsonb)
            from jsonb_array_elements_text(guildapplication.questions::jsonb) as value
        )
    end
);

alter table guildapplication drop column questions;

alter table guildapplication rename column new_questions to questions;
