export type User={id:number;username:string;display_name:string;email:string;is_admin:boolean};
export type Member={id:number;display_name:string;email:string;active:boolean;created_at:string};
export type Quarter={id:number;year:number;quarter:number;label:string;generated_at:string;is_active:boolean;is_completed:boolean};
export type Plan={id:number;quarter_id:number;from_member_id:number;to_member_id:number;from_name:string;to_name:string;amount:number;acknowledged:boolean};
export type MyPlan={quarter:null|{id:number;label:string};member?:{id:number;display_name:string};outgoing:Plan[];incoming:Plan[]};
